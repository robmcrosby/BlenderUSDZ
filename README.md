# Blender UDSZ file import/export add-on

USDZ file import and export plugin for [Blender](https://www.blender.org), that provides a simple method of importing and exporting models used with Augmented Reality applications.


## Installation

1. Download io_export_usdz.zip file from the root of this repository.
2. Open Blender 2.8  and Go to edit -> User Preferences...
3. In User Preferences select Add-ons on the left hand menu and then select the Install button on the top right side of the window.
4. Navigate to and select the downloaded zip file from step 1.
5. Select the check mark next to Import-Export: UDSZ format to activate the plugin.


## Usage

Always be sure to save your work before using this tool.
This tool will attempt to export the currently selected objects in the blender scene. 
The tool can be found in blender under File -> Export -> USDZ (.usdz)
When selected the add-on will present the usual file export window for where to export the  usdz file along with some options on the left side tool bar.
Depending on which options are selected and the size and complexity of the selected objects could affect the amount of time it takes to export a usdz file.


## Add-on Options

### Import Options

Import Materials - By selecting this option, the add-on will attempt to import materials associated with objects.

### Export Options

Export Materials - The exporter will export object materials as USD Principled shader materials which share many of the same properties as the Principled BSDF shader for Eevee and Cycles in Blender. Mix and Add shader nodes are not supported yet in this add-on.

Export Animations - When selected, the active object/bone animation will be exported to the usdz file. Currently any animations are baked per-frame.

Bake Textures - When enabled, any textures associated with materials will be baked out to image files that will be bundled into the usdz file. Currently the add-on will automatically switch to Cycles to bake images which could take a significant amount of time. This option is ignored if Export Materials is unchecked.

Bake AO - This options bakes ambient occlusion textures that are applied to the USD Principled shader materials in the usdz file. Activating this option can add a significant amount of time to export. This option is ignored if Export Materials is unchecked.

Samples - The number of samples used in baking the ambient occlusion textures. A higher number generates higher quality occlusion textures with added time to export. This option is ignored if either Export Materials or Bake AO options are unchecked.

Scale - This value is used to scale the objects exported to the usdz file.

Use Usdz Converter Tool - By selecting this option, the add-on will export a usda file that will be converted to usdz by the external Usdz Converter Tool bundled with Xcode. Note that the Usdz Converter has been deprecated from the current version of Xcode and this option will no longer work.

## Notes

This add-on has only been tested to work on Mac-OS and there are no guarantees that it will work on Windows or Linux.

The generated binary usd file used in the exported usdz file could potentially be incompatible to some augmented reality applications, in these cases it is recommend to export the text version of a usd file by adding the ".usda" extension to the exported file name. Then use the usdconvert tool in usdpython to generate the final usdz file.

The import functionality is currently limited to simple static models with no animations.

