
from collections import Counter

MAX_BLOCK_INPUT_SIZE = 0x7E000000

MAX_OFFSET = 65535
MIN_MATCH = 4
MFLIMIT = 12


def decodeStrings(data, count, encoding='utf-8'):
    strings = []
    while count > 0:
        p = data.find(0)
        if p < 0:
            break
        strings.append(data[:p].decode(encoding))
        data = data[p+1:]
        count -= 1
    return strings

def encodeStrings(strings, encoding='utf-8'):
    data = bytearray()
    for str in strings:
        data += str.encode(encoding) + b'\x00'
    return data


def decodeInts(data, count, size, byteorder='little', signed=False):
    ints = []
    for i in range(count):
        if i * size > len(data):
            print('Over Run Data')
            break
        value = int.from_bytes(data[i*size:i*size + size], byteorder, signed=signed)
        ints.append(value)
    return ints

def encodeInts(ints, size, byteorder='little', signed=False):
    data = bytearray()
    for i in ints:
        data += i.to_bytes(size, byteorder, signed=signed)
    return data


class PositionTable:
    TABLE_SIZE = 4096

    def __init__(self):
        self.table = [None] * self.TABLE_SIZE

    @staticmethod
    def _hash(val):
        val = val & 0x0FFFFFFFF  # prune to 32 bit
        return (val * 2654435761) & 0x0FFF  # max = 4095

    def getPosition(self, val):
        index = self._hash(val)
        return self.table[index]

    def setPosition(self, val, pos):
        index = self._hash(val)
        self.table[index] = pos


def worstCaseBlockLength(srcLen):
    return srcLen + (srcLen // 255) + 16

def readLeUint32(buf, pos):
    return int.from_bytes(buf[pos:pos+4], 'little')

def writeLeUint16(buf, i, val):
    buf[i] = val & 0x00FF
    buf[i + 1] = (val >> 8) & 0x00FF

def writeLeUint32(buf, i, val):
    buf[i] = val & 0x000000FF
    buf[i + 1] = (val >> 8) & 0x000000FF
    buf[i + 2] = (val >> 16) & 0x000000FF
    buf[i + 3] = (val >> 24) & 0x000000FF

def findMatch(table, val, src, srcPtr):
    pos = table.getPosition(val)
    if pos is not None and val == readLeUint32(src, pos):
        # Check if the match is too far away
        if srcPtr - pos > MAX_OFFSET:
            return None
        else:
            return pos
    else:
        return None


def countMatch(buf, front, back, max):
    count = 0
    while back <= max:
        if buf[front] == buf[back]:
            count += 1
        else:
            break
        front += 1
        back += 1
    return count


def copySequence(dst, dstHead, literal, match):
    litLen = len(literal)
    dstPtr = dstHead

    # Write the length of the literal
    token = memoryview(dst)[dstPtr:dstPtr + 1]
    dstPtr += 1
    if litLen >= 15:
        token[0] =  (15 << 4)
        remLen = litLen - 15
        while remLen >= 255:
            dst[dstPtr] = 255
            dstPtr += 1
            remLen -= 255
        dst[dstPtr] = remLen
        dstPtr += 1
    else:
        token[0] = (litLen << 4)

    # Write the literal
    dst[dstPtr:dstPtr + litLen] = literal
    dstPtr += litLen

    offset, matchLen = match
    if matchLen > 0:
        # Write the Match offset
        writeLeUint16(dst, dstPtr, offset)
        dstPtr += 2

        # Write the Match length
        matchLen -= MIN_MATCH
        if matchLen >= 15:
            token[0] = token[0] | 15
            matchLen -= 15
            while matchLen >= 255:
                dst[dstPtr] = 255
                dstPtr += 1
                matchLen -= 255
            dst[dstPtr] = matchLen
            dstPtr += 1
        else:
            token[0] = token[0] | matchLen
    return dstPtr - dstHead


def lz4CompressDefault(src):
    srcLen = len(src)
    if srcLen > MAX_BLOCK_INPUT_SIZE:
        return b''
    dst = bytearray(worstCaseBlockLength(srcLen))
    posTable = PositionTable()
    srcPtr = 0
    literalHead = 0
    dstPtr = 0
    MAX_INDEX = srcLen - MFLIMIT

    while srcPtr < MAX_INDEX:
        curValue = readLeUint32(src, srcPtr)
        matchPos = findMatch(posTable, curValue, src, srcPtr)
        if matchPos is not None:
            length = countMatch(src, matchPos, srcPtr, MAX_INDEX)
            if length < MIN_MATCH:
                break
            dstPtr += copySequence(dst, dstPtr,
                                   memoryview(src)[literalHead:srcPtr],
                                   (srcPtr - matchPos, length))
            srcPtr += length
            literalHead = srcPtr
        else:
            posTable.setPosition(curValue, srcPtr)
            srcPtr += 1
    # Write the last literal
    dstPtr += copySequence(dst, dstPtr,
                           memoryview(src)[literalHead:srcLen],
                           (0, 0))
    return dst[:dstPtr]

def lz4Compress(src):
    dst = bytearray()
    inputSize = len(src)
    if inputSize == 0:
        return dst
    if inputSize > 127 * MAX_BLOCK_INPUT_SIZE:
        print('Buffer Too Large for LZ4 Compression')
    elif inputSize <= MAX_BLOCK_INPUT_SIZE:
        dst.append(0)
        dst += lz4CompressDefault(src)
    else:
        wholeChunks = inputSize // MAX_BLOCK_INPUT_SIZE
        partChunkSize = inputSize % MAX_BLOCK_INPUT_SIZE
        partChunk = 1 if partChunkSize > 0 else 0
        dst = (wholeChunks+partChunk).to_bytes(1, byteorder='little')
        for i in range(wholeChunks):
            offset = i * MAX_BLOCK_INPUT_SIZE
            chunk = src[offset:offset+MAX_BLOCK_INPUT_SIZE]
            chunk = lz4CompressDefault(chunk)
            dst += (len(chunk)).to_bytes(4, byteorder='little')
            dst += chunk
        if partChunk == 1:
            offset = wholeChunks * MAX_BLOCK_INPUT_SIZE
            chunk = src[offset:]
            chunk = lz4CompressDefault(chunk)
            dst += (len(chunk)).to_bytes(4, byteorder='little')
            dst += chunk
    return dst


def lz4DecompressChunk(src):
    dst = bytearray()
    srcLen = len(src)
    srcPtr = 0
    while srcPtr < srcLen:
        token = memoryview(src)[srcPtr:srcPtr +  1]
        srcPtr += 1
        # Get Literal Length
        litLen = (token[0] >> 4) & 0x0F
        if litLen == 15:
            while src[srcPtr] == 255:
                litLen += 255
                srcPtr += 1
            litLen += src[srcPtr]
            srcPtr += 1
        # Copy Literal
        dst += src[srcPtr:srcPtr + litLen]
        srcPtr += litLen
        # Reached Last Literal
        if srcPtr >= srcLen:
            break
        # Get match offset
        offset = int.from_bytes(src[srcPtr:srcPtr + 2], 'little')
        srcPtr += 2
        # Get match length
        matchLen = token[0] & 0x0F
        if matchLen == 15:
            while src[srcPtr] == 255:
                matchLen += 255
                srcPtr += 1
            matchLen += src[srcPtr]
            srcPtr += 1
        matchLen += MIN_MATCH
        # Copy Match
        for i in range(matchLen):
            dst.append(dst[len(dst) - offset])
    return dst


def lz4Decompress(src):
    dst = bytearray()
    if len(src) > 0:
        if src[0] == 0:
            dst = lz4DecompressChunk(memoryview(src)[1:])
        else:
            chunkSize = int.from_bytes(src[:4], 'little') - 1
            #print('chunkSize', chunkSize)
            srcPtr = 9
            while chunkSize > 0:
                dst += lz4DecompressChunk(memoryview(src)[srcPtr:srcPtr+chunkSize])
                srcPtr += chunkSize
                if srcPtr + 8 < len(src):
                    srcPtr += 1
                    chunkSize = int.from_bytes(src[srcPtr:srcPtr + 4], 'little')
                    #print('chunkSize', chunkSize)
                    srcPtr += 8
                else:
                    chunkSize = 0
    return dst


def usdInt32Compress(values):
    values = values.copy()
    data = bytearray()
    if len(values) == 0:
        return data
    preValue = 0
    for i in range(len(values)):
        value = values[i]
        values[i] = value - preValue
        preValue = value
    commonValue = Counter(values).most_common()[0][0]
    data += commonValue.to_bytes(4, 'little', signed=True) + data
    data += bytes((len(values) * 2 + 7) // 8)
    for v in range(len(values)):
        value = values[v]
        i = v + 16
        if value != commonValue:
            if value.bit_length() < 8:
                data[i//4] |= 1 << ((i%4)*2)
                data += value.to_bytes(1, 'little', signed=True)
            elif value.bit_length() < 16:
                data[i//4] |= 2 << ((i%4)*2)
                data += value.to_bytes(2, 'little', signed=True)
            else:
                data[i//4] |= 3 << ((i%4)*2)
                data += value.to_bytes(4, 'little', signed=True)
    return data


def usdInt32Decompress(data, numInts):
    values = []
    numCodes = (numInts * 2 + 7) // 8
    commonValue = int.from_bytes(data[:4], 'little', signed=True)
    data = data[4:]
    codes = memoryview(data)[:numCodes]
    vints = memoryview(data)[numCodes:]
    preValue = 0
    cp = 0
    vp = 0
    while cp < numInts:
        code = (codes[cp//4] >> (cp%4)*2) & 0x3
        if code == 0:
            preValue += commonValue
        elif code == 1:
            preValue += int.from_bytes(vints[vp:vp+1], 'little', signed=True)
            vp += 1
        elif code == 2:
            preValue += int.from_bytes(vints[vp:vp+2], 'little', signed=True)
            vp += 2
        else:
            preValue += int.from_bytes(vints[vp:vp+4], 'little', signed=True)
            vp += 4
        values.append(preValue)
        cp += 1
    return values


def usdInt64Decompress(data, numInts):
    values = []
    numCodes = (numInts * 2 + 7) // 8
    commonValue = int.from_bytes(data[:8], 'little', signed=True)
    data = data[8:]
    codes = memoryview(data)[:numCodes]
    vints = memoryview(data)[numCodes:]
    preValue = 0
    cp = 0
    vp = 0
    while cp < numInts:
        code = (codes[cp//4] >> (cp%4)*2) & 0x3
        if code == 0:
            preValue += commonValue
        elif code == 1:
            preValue += int.from_bytes(vints[vp:vp+2], 'little', signed=True)
            vp += 2
        elif code == 2:
            preValue += int.from_bytes(vints[vp:vp+4], 'little', signed=True)
            vp += 4
        else:
            preValue += int.from_bytes(vints[vp:vp+8], 'little', signed=True)
            vp += 8
        values.append(preValue)
        cp += 1
    return values
