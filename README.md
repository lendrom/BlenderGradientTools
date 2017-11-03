# BlenderGradientTools
Python addon for importing gradients from svg, css and ggr gradient definitions
#1. About the addon
#Addon that allows for import of SVG, GGR and CSS files with definition of linearGradient as input of ColorRamps nodes color stops.
#The tool is active when a ColorRamp node is selected and active. Note that Blender has limitation of 32 color stops per ColorRamp node.
#In order to import a bigger color ramp (no matter the input format) option 'replace ColorRamp with group for bigger gradients'. It will
#replace active color ramp node with a group that creates gradients with more than 32 color stops. Groups must be created also for gradients
#that have non uniform interpolation (e.g. ggr files can have different interpolations for every 3-color stop segment). Be warned, that really
#big gradients will crash Blender. I guess it depends on your system. The 32 color stops limit could have been set for a reason...

#2. SVG support
#The addon will scan through choosen svg file for linearGradient definition and will add its color stops
#to the active node. Only the first gradient definiton found in the file will be considered.
#A great resource for svg gradients definitions is cpt-city site:
#http://soliton.vm.bytemark.co.uk/pub/cpt-city/index.html

#3. GGR support
#The addon will allow for import of GIMP created gradients, which may be quite complex. Not all GGR properties are supported.
#GGR format documentation:
#https://github.com/mirecta/gimp/blob/master/devel-docs/ggr.txt
#GIMP Gradients editor:
#https://docs.gimp.org/en/gimp-gradient-dialog.html#gimp-gradient-editor-dialog

#4. CSS support
#The addon will import -moz-linear-gradient and -webkit-linear-gradient from a css file. Only the first gradient definiton
#found in the file will be considered.
#Some tools for generating css gradines that are available online were pointed out to me:
#http://www.gradient-scanner.com/
#http://www.colorzilla.com/gradient-editor/#_
#http://www.kmhcreative.com/downloads/CSS2SVG.htm
#CSS syntax:
#https://developer.mozilla.org/en-US/docs/Web/CSS/linear-gradient#Formal_syntax