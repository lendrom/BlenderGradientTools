#-*- coding:utf-8 -*-

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

bl_info = {
    "name": "Import gradients from svg, ggr, css to color ramp node",
    "author": "Lech Karłowicz",
    "version": (0, 8),
    "blender": (2, 76, 0),
    "location": "Node Editor -> Right shelf panel (Color ramp)",
    "description": "Addon that allows for import of SVG, GGR, CSS files with definition of gradient as input of ColorRamps nodes color stops or as groups replacing ColorRamps.",
    "warning": "",
    "wiki_url": "",
    "tracker_url": "",
    "category": "Node"}


#Blender
#enum in [‘EASE’, ‘CARDINAL’, ‘LINEAR’, ‘B_SPLINE’, ‘CONSTANT’], default ‘LINEAR’
#Gimp
#Blending function (enum; values are: 0 = "linear" 1 = "curved" 2 = "sinusoidal" 3 = "spherical (increasing)" 4 = "spherical (decreasing)")

INTERPOLATIONS = {
            0:                  #RGB: ‘EASE’, ‘CARDINAL’, ‘LINEAR’, ‘B_SPLINE’, ‘CONSTANT’
            {
                0 : 'LINEAR',
                1 : 'LINEAR', #"curved"
                2 : 'LINEAR', #"sinusoidal"
                3 : 'LINEAR', #"spherical (increasing)"
                4 : 'LINEAR', #"spherical (decreasing)"
                 },
            1:                  #HSV CCW
            {
                0 : 'CW',       #seams that it must be opposite to GIMP
                },
            2:                  #HSV CW
            {
                0 : 'CCW',   #seams that it must be opposite to GIMP
                }
}
#Blender
#enum in [‘RGB’, ‘HSV’, ‘HSL’], default ‘RGB’
#Gimp
#Coloring type (enum; values are: 0 = "RGB" 1 = "HSV CCW" 2 = "HSV CW")

COLOR_MODES = {
            0 : "RGB",
            1 : "HSV",
            2 : "HSV",
}



nodeTypes = {
    'CompositorNodeTree':
    {
        'math':'CompositorNodeMath',
        'colorRamp':'CompositorNodeValToRGB',
        'separateRGB':'CompositorNodeSepRGBA',
        'combineRGB':'CompositorNodeCombRGBA',
        'mixRGB':'CompositorNodeMixRGB',
        },
    'ShaderNodeTree':
    {
        'math':'ShaderNodeMath',
        'colorRamp':'ShaderNodeValToRGB',
        'separateRGB':'ShaderNodeSeparateRGB',
        'combineRGB':'ShaderNodeCombineRGB',
        'mixRGB':'ShaderNodeMixRGB',
        },
    'TextureNodeTree':
    {
        'math':'TextureNodeMath',
        'colorRamp':'TextureNodeValToRGB',
        'separateRGB':'TextureNodeDecompose',
        'combineRGB':'TextureNodeCompose',
        'mixRGB':'TextureNodeMixRGB',
        }
    }





import bpy
from bpy_extras.io_utils import ImportHelper
from bpy.props import StringProperty, BoolProperty, EnumProperty, FloatVectorProperty, IntProperty
from bpy.types import Operator
from xml.dom.minidom import parse
from math import sqrt
import os



def stripEOLs(stringIn):
    stringOut = stringIn.replace('\n','')
    #print(stringOut)
    return stringOut


def stripComments(stringIn):
    currCommentStart = -1
    currCommentStop = -1
    comments = []
    for i in range(0,len(stringIn)):
        if stringIn[i] == r'/':
            if i < len(stringIn)-1:
                if stringIn[i+1] == '*':
                    currCommentStart = i
            if stringIn[i-1] == '*':
                currCommentStop = i+1
                comments.append((currCommentStart,currCommentStop))
                currCommentStart = -1
                currCommentStop = -1
                
    if currCommentStart != -1 and currCommentStop == -1:
        print("Not closed comment?")
    offset = 0
    stringOut = stringIn
    #print(comments)
    for c in comments:
        #print(str(offset))
        #print(stringOut)
        stringOut = stringOut[:c[0]-offset]+stringOut[c[1]-offset:]
        offset += (c[1]-c[0])

    return stringOut

def stripSelectors(linesIn):
    #get rid of css selectors as they are not needed for our purposes
    linesOut = []
    for l in linesIn:
        l = l.rstrip()
        if ':' in l:
            l = l.rpartition(':')[2].lstrip()
        linesOut.append(l)
    return linesOut

#print
def css2gradient(filepath,useAlpha = True):
    f = open(filepath,'r')
    cssString = f.read()
    f.close()

    #print(cssString)
    
    cssStatements = stripSelectors((stripEOLs(stripComments(cssString))).split(';'))

    print(cssStatements)
    
    for s in cssStatements:
        #print(s)
        if s.startswith('-webkit-linear-gradient') or s.startswith('-moz-linear-gradient'):
            return parseCss(s, useAlpha)

def angle(string):
    for unit in ['deg','grad','rad','turn']:
        if unit in string:
            return True
    for d in ['top','bottom','left','right']:
        if d in string:
            return True

    return False

def cssPosition(string):
    if '%' in string:
        position = float(string.split('%')[0])/100
    else:
        position = float(string)
    return position

def cssColor(string):
    if string in cssColors.keys():
        return cssColors.get(string)
    else:
        if string[0] == '#':
            return hex_to_rgb(string)
        else:
            if string.startswith('rgb'):
                return [float(c)/255.0 for c in string[string.index('(')+1:string.index(')')].split(',')]
            elif string.startswith('rgba'):
                values = string[string.index('(')+1:string.index(')')].split(',')
                return [float(values[0])/255.0,float(values[1])/255.0,float(values[2])/255.0,float(values[3])]
            elif string.startswith('hsl'):

                import colorsys
                values = string[string.index('(')+1:string.index(')')].split(',')
                hue_normalized = float(((float(values[0]) % 360) + 360) % 360)/360.0
                lightness_normalized = float(values[2].replace('%',''))/100.0
                saturation_normalized = float(values[1].replace('%',''))/100.0 
                rgb = colorsys.hls_to_rgb(hue_normalized,lightness_normalized,saturation_normalized)
                return [rgb[0],rgb[1],rgb[2]]
            elif string.startswith('hsla'):
                import colorsys
                values = string[string.index('(')+1:string.index(')')].split(',')
                hue_normalized = float(((float(values[0]) % 360) + 360) % 360)/360.0
                lightness_normalized = float(values[2].replace('%',''))/100.0
                saturation_normalized = float(values[1].replace('%',''))/100.0
                alpha = float(values[3])
                rgb = colorsys.hls_to_rgb(hue_normalized,lightness_normalized,saturation_normalized)
                return [rgb[0],rgb[1],rgb[2],alpha]
            else:
                return [0,0,0,1]

def getSvgAttribute(node,attribute):
    result = node.getAttribute(attribute)
    if result in (None,'',' '): #if the attribute was not found, try find it as a style attribute value
        style = stop.getAttribute('style')
        result = cssStyleAttribute(style,attribute)
        return result
    else:
        return result
    

def cssStyleAttribute(css_definition, css_attribute):
    css_definition = css_definition.replace(' ','') #strip spaces
    start_index = css_definition.find(css_attribute) #find start of the css attribute
    if start_index == -1:
        return ''
    else:
        end_index = css_definition.find(';',start_index) #find ending comma or -1
        searched_attrib = css_definition[start_index:end_index] #searched attrib
        searched_value = searched_attrib.split(':')[1] #searched value
        return searched_value


def svg2gradient(svg,use_alpha):
    n = 0
    
    try:
        domData = parse(svg)
    except:
        return []
    
    linearGradient = domData.getElementsByTagName('linearGradient')[0]
    
    gradientData = []
    
    for stop in linearGradient.getElementsByTagName('stop'):
        #print("ELEMENT "+str(n))
        n+=1
        if n == 1:
            color_string = getSvgAttribute(stop,'stop-color')
                
            if color_string[0] == '#':
                #tuple(ord(c) for c in color_string[1:].decode('hex'))
                #struct.unpack('BBB',color_string[1:].decode('hex'))
                prevColor =  hex_to_rgb(color_string)
                #print(str(color))
            else:
                prevColor = list(float(c)/255 for c in color_string.replace('rgb(','').replace(')','').split(','))
            prevColor.append(1.0)
            prevColor = tuple(prevColor)
                
            if use_alpha:
                opacity = getSvgAttribute(stop,'stop-opacity')
                if opacity == '':
                    prevAlpha = 1.0
                else:
                    prevAlpha = float(opacity)
            else:
                prevAlpha = 1.0
            prevStop = 0.0
            #prevColor = list(float(c)/255 for c in stop.getAttribute('stop-color').replace('rgb(','').replace(')','').split(','))
            prevColorR = prevColor[0]
            prevColorG = prevColor[1]
            prevColorB = prevColor[2]
            #if use_alpha:
            #    prevAlpha = float(stop.getAttribute('stop-opacity'))
            #else:
            #    prevAlpha = 1.0
        else:
            leftEndpointCoordinate = prevStop
            rightEndpointCoordinate = float(stop.getAttribute('offset').split('%')[0])/100.0
            #midpointCoordinate = leftEndpointCoordinate+((rightEndpointCoordinate-leftEndpointCoordinate)/2)
            midpointCoordinate = -1.0 #no point in creating
            #color = list(float(c)/255 for c in stop.getAttribute('stop-color').replace('rgb(','').replace(')','').split(','))
            color_string = getSvgAttribute(stop,'stop-color')

            if color_string[0] == '#':
                #tuple(ord(c) for c in color_string[1:].decode('hex'))
                #struct.unpack('BBB',color_string[1:].decode('hex'))
                color =  hex_to_rgb(color_string)
                #print(str(color))
            else:
                color = list(float(c)/255 for c in color_string.replace('rgb(','').replace(')','').split(','))
            color.append(1.0)
            color = tuple(color)
                
            if use_alpha:
                opacity = getSvgAttribute(stop,'stop-opacity')
                
                if opacity == '':
                    alpha = 1
                else:
                    alpha = float(opacity)
            else:
                alpha = 1.0
                
            colorR = color[0]
            colorG = color[1]
            colorB = color[2]
##            if use_alpha:
##                alpha = float(stop.getAttribute('stop-opacity'))
##            else:
##                alpha = 1.0
            gradientData.append(
                {
                    'leftEndpointCoordinate':leftEndpointCoordinate,
                    'midpointCoordinate':midpointCoordinate,
                    'rightEndpointCoordinate':rightEndpointCoordinate,
                    'prevColorR':prevColorR,
                    'prevColorG':prevColorG,
                    'prevColorB':prevColorB,
                    'prevAlpha':prevAlpha,
                    'colorR':colorR,
                    'colorG':colorG,
                    'colorB':colorB,
                    'alpha':alpha,
                    'interpolation':0,
                    'coloringType':0,
                 }
                )

            prevStop = rightEndpointCoordinate
            prevColorR = colorR
            prevColorG = colorG
            prevColorB = colorB
            prevAlpha = alpha
    domData.unlink()        
    return gradientData
            
def ggr2gradient(filepath,use_alpha,color_fg,color_bg):
    
    f = open(filepath,'r')
    ggr = f.read()
    f.close()
    
    ggr_input = ggr.splitlines()
    if ggr_input[0] == 'GIMP Gradient':
        gradientName = ggr_input[1].replace('Name: ','')
        gradientDataTmp = [f.split() for f in ggr_input[3:3+int(ggr_input[2])]]
        gradientData = []
        for row in gradientDataTmp:
            #print(str(len(row)))
            if use_alpha:
                alpha = float(row[10])
                prevAlpha = float(row[6])
            else:
                alpha = 1.0
                prevAlpha = 1.0
            if len(row) == 15: #if there are foreground/background definitions for the row (segment) stops
                #print("14")
                if row[13] != '0': #first stop
                    if row[13] in ('1','2'): #foreground color
                        row[3] = color_fg[0]
                        row[4] = color_fg[1]
                        row[5] = color_fg[2]
                    elif row[13] in ('3','4'): #background color
                        row[3] = color_bg[0]
                        row[4] = color_bg[1]
                        row[5] = color_bg[2]
                    if row[13] in ('2','4'):
                        prevAlpha = 0.0
                if row[14] != '0':
                    if row[14] in ('1','2'): #foreground color
                        row[7] = color_fg[0]
                        row[8] = color_fg[1]
                        row[9] = color_fg[2]
                    elif row[14] in ('3','4'): #background color
                        row[7] = color_bg[0]
                        row[8] = color_bg[1]
                        row[9] = color_bg[2]
                    if row[14] in ('2','4'):
                        prevAlpha = 0.0
            if float(row[1]) != (float(row[0])+((float(row[0]) - float(row[2]))/2.0)):
                midpointCoordinate = float(row[1])
            else:
                midpointCoordinate = -1
            gradientData.append(
                {
                    'leftEndpointCoordinate':float(row[0]),
                    'midpointCoordinate':midpointCoordinate,
                    'rightEndpointCoordinate':float(row[2]),
                    'prevColorR':float(row[3]),
                    'prevColorG':float(row[4]),
                    'prevColorB':float(row[5]),
                    'prevAlpha':prevAlpha,
                    'colorR':float(row[7]),
                    'colorG':float(row[8]),
                    'colorB':float(row[9]),
                    'alpha':alpha,
                    'interpolation':int(row[11]),
                    'coloringType':int(row[12]),
                 }
                )
        return gradientData

def parseCss(line, useAlpha = True):
    #line = parseCss(filepath,useAlpha)
    
    stops = [l.lstrip() for l in line[line.index('(')+1:line.index(')')].split(',')]
    if angle(stops[0]): #direction - we don't need that so we ignore it
        stops = stops[1:]
    n = 0
    gradientData = []
    #print(str(stops))
    for s in stops:
        n += 1
        stopDef = s.split(' ')
        stopColor = cssColor(stopDef[0])
        
        alpha = 1.0
        if useAlpha:
            if len(stopColor) == 4:
                alpha = stopColor[3]
        if n != 1:
            if len(stopDef) > 1:
                rightEndpointCoordinate = cssPosition(stopDef[1])
            else:
                rightEndpointCoordinate = float((n-1)/len(stops))
            gradientData.append(
                {
                    'leftEndpointCoordinate':prevRightEndpointCoordinate,
                    'midpointCoordinate':-1,
                    'rightEndpointCoordinate':rightEndpointCoordinate,
                    'prevColorR':prevColorR,
                    'prevColorG':prevColorG,
                    'prevColorB':prevColorB,
                    'prevAlpha':prevAlpha,
                    'colorR':stopColor[0],
                    'colorG':stopColor[1],
                    'colorB':stopColor[2],
                    'alpha':alpha,
                    'interpolation':0,
                    'coloringType':0,
                 }
                )
            prevColorR = stopColor[0]
            prevColorG = stopColor[1]
            prevColorB = stopColor[2]
            prevRightEndpointCoordinate = rightEndpointCoordinate
            #prevAlpha
        else:
            if len(stops) == 1:
                gradientData.append(
                    {
                        'leftEndpointCoordinate':0.0,
                        'midpointCoordinate':-1,
                        'rightEndpointCoordinate':1.0,
                        'prevColorR':stopColor[0],
                        'prevColorG':stopColor[1],
                        'prevColorB':stopColor[2],
                        'prevAlpha':alpha,
                        'colorR':stopColor[0],
                        'colorG':stopColor[1],
                        'colorB':stopColor[2],
                        'alpha':alpha,
                        'interpolation':0,
                        'coloringType':0,
                     }
                    )                

            else:            
                prevColorR = stopColor[0]
                prevColorG = stopColor[1]
                prevColorB = stopColor[2]
                prevAlpha = alpha
                prevRightEndpointCoordinate = 0.0
        #print(s)
    return gradientData


# from node wrangler
def nw_check(context):
    space = context.space_data
    valid = False
    if space.type == 'NODE_EDITOR' and space.node_tree is not None:
        valid = True
        
    return valid 



def groupFromGradient(gradientData,gradientName,nodeTreeType,tree, nodeOrigin = (0,0),nodeSpacing=600,alpha_supported=True):
    #group = bpy.data.node_groups.new(type="ShaderNodeTree", name=gradientName)
    group = bpy.data.node_groups.new(type=nodeTreeType, name=gradientName)
    #group = bpy.data.node_groups.new(type="CompositorNodeTree", name=gradientName)
    group.name = gradientName
    
    
    group.inputs.new("NodeSocketFloat", "Factor")
    input_node = group.nodes.new("NodeGroupInput")
    input_node.location = nodeOrigin
    group.outputs.new("NodeSocketColor","Color")
    if alpha_supported:
        alpha = group.outputs.new("NodeSocketFloat","Alpha")
        alpha.default_value = 1.0
    output_node = group.nodes.new("NodeGroupOutput")
    output_node.location = (7000+((len(gradientData)-1)*nodeSpacing), 0)

    #factor_node = group.nodes.new(type='ShaderNodeMath')
    factor_node = group.nodes.new(type=nodeTypes.get(nodeTreeType).get('math'))#'ShaderNodeMath')
    factor_node.name = "Factor input"    
    factor_node.operation = "MULTIPLY"
    factor_node.location = (nodeOrigin[0]+nodeSpacing,nodeOrigin[1])
    factor_node.inputs[1].default_value = 1.0
    group.links.new(input_node.outputs["Factor"], factor_node.inputs[0])
    
    n = 0
    for row in gradientData:
        n += 1
        #print('Start '+str(n))
        if n > 1:
            
            group.inputs.new("NodeSocketFloat", "ColorStop_"+str(n-1))
            #group.inputs[n-1].default_value = float(row[0])
            group.inputs[n-1].default_value = float(row["leftEndpointCoordinate"])
            #color stop multiply by 1
            #curr_stop_node = group.nodes.new(type='ShaderNodeMath')
            curr_stop_node = group.nodes.new(type=nodeTypes.get(nodeTreeType).get('math'))
            curr_stop_node.operation = "MULTIPLY"
            curr_stop_node.name = "ColorStop_"+str(n)
            curr_stop_node.inputs[1].default_value = 1.0
            curr_stop_node.location = (nodeOrigin[0]+(nodeSpacing),nodeOrigin[1]-((n-1)*nodeSpacing))
            group.links.new(input_node.outputs["ColorStop_"+str(n-1)], curr_stop_node.inputs[0])
            group.links.new(curr_stop_node.outputs[0],prev_lt_node.inputs[1])
            
            #greater than node
            #curr_gt_node = group.nodes.new(type='ShaderNodeMath')
            curr_gt_node = group.nodes.new(type=nodeTypes.get(nodeTreeType).get('math'))
            curr_gt_node.operation = "GREATER_THAN"
            curr_gt_node.name = "Greater than "+str(n)
            if n == len(gradientData):
                curr_gt_node.location = (nodeOrigin[0]+(2*nodeSpacing),nodeOrigin[1]-((n-1)*nodeSpacing))
                curr_mask = curr_gt_node
            else:
                curr_gt_node.location = (nodeOrigin[0]+(2*nodeSpacing),nodeOrigin[1]-((n-1)*nodeSpacing)-(nodeSpacing/4))
            group.links.new(factor_node.outputs[0], curr_gt_node.inputs[0])
            group.links.new(curr_stop_node.outputs[0], curr_gt_node.inputs[1])
            
            #two subtract nodes
            #curr_subtr1_node = group.nodes.new(type='ShaderNodeMath')
            curr_subtr1_node = group.nodes.new(type=nodeTypes.get(nodeTreeType).get('math'))
            curr_subtr1_node.operation = "SUBTRACT"
            curr_subtr1_node.name = "Subtract 1 "+str(n)
            curr_subtr1_node.location = (nodeOrigin[0]+(4*nodeSpacing),nodeOrigin[1]-((n-1)*nodeSpacing)+(nodeSpacing/4))            
            
            group.links.new(factor_node.outputs[0],curr_subtr1_node.inputs[0])
            group.links.new(curr_stop_node.outputs[0],curr_subtr1_node.inputs[1])

            #curr_subtr2_node = group.nodes.new(type='ShaderNodeMath')
            curr_subtr2_node = group.nodes.new(type=nodeTypes.get(nodeTreeType).get('math'))
            curr_subtr2_node.operation = "SUBTRACT"
            curr_subtr2_node.name = "Subtract 2 "+str(n)
            curr_subtr2_node.inputs[0].default_value = 1.0
            curr_subtr2_node.location = (nodeOrigin[0]+(4*nodeSpacing),nodeOrigin[1]-((n-1)*nodeSpacing)-(nodeSpacing/4))
            
            group.links.new(curr_stop_node.outputs[0],curr_subtr2_node.inputs[1])
            
            if n > 2:
                #group.links.new(prev_stop_node.outputs[0],curr_subtr2_node.inputs[0])
                group.links.new(curr_stop_node.outputs[0],prev_subtr2_node.inputs[0])
            if n > 1:
                prev_subtr2_node = curr_subtr2_node
                       
            
        if n < len(gradientData):
            #curr_lt_node = group.nodes.new(type='ShaderNodeMath')
            curr_lt_node = group.nodes.new(type=nodeTypes.get(nodeTreeType).get('math'))
            curr_lt_node.operation = "LESS_THAN"
            curr_lt_node.name = "Less than "+str(n)
            if n > 1:
                curr_lt_node.location = (nodeOrigin[0]+(2*nodeSpacing),nodeOrigin[1]-((n-1)*nodeSpacing)+(nodeSpacing/4))
            else:
                curr_lt_node.location = (nodeOrigin[0]+(2*nodeSpacing),nodeOrigin[1]-((n-1)*nodeSpacing))
                curr_mask = curr_lt_node
            curr_lt_node.inputs[1].default_value = 1.0
            group.links.new(factor_node.outputs[0], curr_lt_node.inputs[0])
            
            prev_lt_node = curr_lt_node
        
        
        if 1 < n < len(gradientData):
            #curr_gtlt_node = group.nodes.new(type='ShaderNodeMath')
            curr_gtlt_node = group.nodes.new(type=nodeTypes.get(nodeTreeType).get('math'))
            curr_gtlt_node.operation = "MULTIPLY"
            curr_gtlt_node.name = "Multiply less and greater than "+str(n)
            curr_gtlt_node.location = (nodeOrigin[0]+(3*nodeSpacing),nodeOrigin[1]-((n-1)*nodeSpacing))        
            group.links.new(curr_lt_node.outputs[0], curr_gtlt_node.inputs[0])
            group.links.new(curr_gt_node.outputs[0], curr_gtlt_node.inputs[1])
            
            curr_mask = curr_gtlt_node

        curr_divide_node = group.nodes.new(type=nodeTypes.get(nodeTreeType).get('math'))
        curr_divide_node.operation = "DIVIDE"
        curr_divide_node.name = "Divide "+str(n)
        curr_divide_node.inputs[1].default_value = 1.0
        curr_divide_node.location = (nodeOrigin[0]+(5*nodeSpacing),nodeOrigin[1]-((n-1)*nodeSpacing))
        
        if n == 1 and len(gradientData) > 1:
            prev_divide_node = curr_divide_node
        
        if n == 2:
            group.links.new(curr_stop_node.outputs[0],prev_divide_node.inputs[1])

        if n > 1:
            group.links.new(curr_subtr1_node.outputs[0],curr_divide_node.inputs[0])
            group.links.new(curr_subtr2_node.outputs[0],curr_divide_node.inputs[1])
        else:
            group.links.new(factor_node.outputs[0],curr_divide_node.inputs[0])


        curr_mask_node = group.nodes.new(type=nodeTypes.get(nodeTreeType).get('math'))
        curr_mask_node.operation = "MULTIPLY"
        curr_mask_node.name = "Mask "+str(n)
        curr_mask_node.location = (nodeOrigin[0]+(6*nodeSpacing),nodeOrigin[1]-((n-1)*nodeSpacing))  

        group.links.new(curr_divide_node.outputs[0], curr_mask_node.inputs[0])
        if len(gradientData) > 1:        
            group.links.new(curr_mask.outputs[0], curr_mask_node.inputs[1])        

        curr_colramp_node = group.nodes.new(type=nodeTypes.get(nodeTreeType).get('colorRamp'))
        curr_colramp_node.name = "ColorRamp "+str(n)
        curr_colramp_node.location = (nodeOrigin[0]+(7*nodeSpacing),nodeOrigin[1]-((n-1)*nodeSpacing))  
        
        group.links.new(curr_mask_node.outputs[0], curr_colramp_node.inputs[0])

        setColorStops(curr_colramp_node,row)
        
        curr_seprgb_node = group.nodes.new(type=nodeTypes.get(nodeTreeType).get('separateRGB'))
        curr_seprgb_node.name = "SeparateRGB "+str(n)
        curr_seprgb_node.location = (nodeOrigin[0]+(8*nodeSpacing),nodeOrigin[1]-((n-1)*nodeSpacing))
        
        group.links.new(curr_colramp_node.outputs[0], curr_seprgb_node.inputs[0])

        curr_maskR_node = group.nodes.new(type=nodeTypes.get(nodeTreeType).get('math'))
        curr_maskR_node.operation = "MULTIPLY"
        curr_maskR_node.name = "Mask Red "+str(n)
        curr_maskR_node.inputs[1].default_value = 1
        curr_maskR_node.location = (nodeOrigin[0]+(9*nodeSpacing),nodeOrigin[1]-((n-1)*nodeSpacing)+(nodeSpacing/3))
        
        group.links.new(curr_seprgb_node.outputs[0], curr_maskR_node.inputs[0])
        if len(gradientData) > 1:
            group.links.new(curr_mask.outputs[0], curr_maskR_node.inputs[1])

        curr_maskG_node = group.nodes.new(type=nodeTypes.get(nodeTreeType).get('math'))
        curr_maskG_node.operation = "MULTIPLY"
        curr_maskG_node.name = "Mask Green "+str(n)
        curr_maskG_node.inputs[1].default_value = 1
        curr_maskG_node.location = (nodeOrigin[0]+(9*nodeSpacing),nodeOrigin[1]-((n-1)*nodeSpacing)) 

        group.links.new(curr_seprgb_node.outputs[1], curr_maskG_node.inputs[0])
        if len(gradientData) > 1:     
            group.links.new(curr_mask.outputs[0], curr_maskG_node.inputs[1])

        curr_maskB_node = group.nodes.new(type=nodeTypes.get(nodeTreeType).get('math'))
        curr_maskB_node.operation = "MULTIPLY"
        curr_maskB_node.name = "Mask Blue "+str(n)
        curr_maskB_node.inputs[1].default_value = 1
        curr_maskB_node.location = (nodeOrigin[0]+(9*nodeSpacing),nodeOrigin[1]-((n-1)*nodeSpacing)-(nodeSpacing/3)) 

        group.links.new(curr_seprgb_node.outputs[2], curr_maskB_node.inputs[0])
        if len(gradientData) > 1:
            group.links.new(curr_mask.outputs[0], curr_maskB_node.inputs[1])

        if alpha_supported:
            curr_maskA_node = group.nodes.new(type=nodeTypes.get(nodeTreeType).get('math'))
            curr_maskA_node.operation = "MULTIPLY"
            curr_maskA_node.name = "Mask Alpha "+str(n)
            curr_maskA_node.inputs[1].default_value = 1
            curr_maskA_node.location = (nodeOrigin[0]+(10*nodeSpacing),nodeOrigin[1]-((n-1)*nodeSpacing)-(nodeSpacing/3)) 

            group.links.new(curr_colramp_node.outputs[1], curr_maskA_node.inputs[0])
            if len(gradientData) > 1:
                group.links.new(curr_mask.outputs[0], curr_maskA_node.inputs[1])

        curr_combrgb_node = group.nodes.new(type=nodeTypes.get(nodeTreeType).get('combineRGB'))
        curr_combrgb_node.name = "CombineRGB "+str(n)
        curr_combrgb_node.location = (nodeOrigin[0]+(10*nodeSpacing),nodeOrigin[1]-((n-1)*nodeSpacing)) 
        
        if n == 1:
            if len(gradientData) > 1:
                prev_rgb_node = curr_combrgb_node
                
                if alpha_supported:
                    prev_alpha_node = curr_maskA_node
            else:
                group.links.new(curr_combrgb_node.outputs[0],output_node.inputs[0])
                
                if alpha_supported:
                    group.links.new(curr_maskA_node.outputs[0],output_node.inputs[1])
        else:
            curr_mixrgb_node = group.nodes.new(type=nodeTypes.get(nodeTreeType).get('mixRGB'))
            curr_mixrgb_node.blend_type = "ADD"
            curr_mixrgb_node.inputs[0].default_value = 1.0
            curr_mixrgb_node.name = "MixRGB "+str(n)
            curr_mixrgb_node.location = (nodeOrigin[0]+(11*nodeSpacing)+((n-2)*nodeSpacing),nodeOrigin[1]-((n-1)*nodeSpacing))
            
            group.links.new(prev_rgb_node.outputs[0],curr_mixrgb_node.inputs[1])
            group.links.new(curr_combrgb_node.outputs[0],curr_mixrgb_node.inputs[2])
            
            if alpha_supported:
                curr_mixA_node = group.nodes.new(type=nodeTypes.get(nodeTreeType).get('math'))
                curr_mixA_node.operation = "ADD"
                curr_mixA_node.name = "MixAlpha "+str(n)
                curr_mixA_node.location = (nodeOrigin[0]+(11*nodeSpacing)+((n-2)*nodeSpacing),nodeOrigin[1]-((n-1)*nodeSpacing)-(nodeSpacing/3))

                group.links.new(prev_alpha_node.outputs[0],curr_mixA_node.inputs[0])
                group.links.new(curr_maskA_node.outputs[0],curr_mixA_node.inputs[1])
                                             
            if n == len(gradientData):
                group.links.new(curr_mixrgb_node.outputs[0],output_node.inputs[0])
                if alpha_supported:
                    group.links.new(curr_mixA_node.outputs[0],output_node.inputs[1])
            else:
                prev_rgb_node = curr_mixrgb_node
                if alpha_supported:
                    prev_alpha_node = curr_mixA_node
        
        group.links.new(curr_maskR_node.outputs[0], curr_combrgb_node.inputs[0])
        group.links.new(curr_maskG_node.outputs[0], curr_combrgb_node.inputs[1])
        group.links.new(curr_maskB_node.outputs[0], curr_combrgb_node.inputs[2])

    if nodeTreeType == "CompositorNodeTree":
        group_node = tree.nodes.new("CompositorNodeGroup")
    if nodeTreeType == "ShaderNodeTree":
        group_node = tree.nodes.new("ShaderNodeGroup")
    if nodeTreeType == "TextureNodeTree":
        group_node = tree.nodes.new("TextureNodeGroup")
    group_node.name = gradientName
    group_node.node_tree = group        

    return group_node.name

def setColorStops(node,row):
    #print(str(row))
    clearColorRamp(node)
    coloringType = COLOR_MODES.get(int(row['coloringType']),'RGB')

    n = 0
    stopsRange = float(row['rightEndpointCoordinate']) - float(row['leftEndpointCoordinate'])
    if coloringType == 'RGB':
        node.color_ramp.interpolation = INTERPOLATIONS.get(int(row['coloringType'])).get(int(row['interpolation']),'LINEAR')
    elif coloringType == 'HSV':
        hueInterpolation = INTERPOLATIONS.get(int(row['coloringType'])).get(int(row['interpolation']),'CW')
        node.color_ramp.hue_interpolation = hueInterpolation
    else:
        pass  
    for stop in row['stops']:
        n += 1
        if n == 1:
            #print('first stop: '+str((float(stop['leftEndpointCoordinate'])-float(row['leftEndpointCoordinate']))/float(stopsRange)))
            firstStop = node.color_ramp.elements[0]
            firstStop.position = (float(stop['leftEndpointCoordinate'])-float(row['leftEndpointCoordinate']))/float(stopsRange)
            firstStop.color = (float(stop['prevColorR']),float(stop['prevColorG']),float(stop['prevColorB']),float(stop['prevAlpha']))
        else:
            currLeftColor = (float(stop['prevColorR']),float(stop['prevColorG']),float(stop['prevColorB']),float(stop['prevAlpha']))
            if prevRightColor != currLeftColor:
                firstStop = node.color_ramp.elements.new(1)
                firstStop.position = (float(stop['leftEndpointCoordinate'])-float(row['leftEndpointCoordinate']))/float(stopsRange)
                firstStop.color = currLeftColor
                
        #print('next stop: '+str((float(stop['rightEndpointCoordinate'])-float(row['leftEndpointCoordinate']))/float(stopsRange)))
        currStopPos = (float(stop['rightEndpointCoordinate'])-float(row['leftEndpointCoordinate']))/float(stopsRange)
        #currStop = node.color_ramp.elements.new(currStopPos)
        currStop = node.color_ramp.elements.new(1)
        currStop.position = currStopPos
        currStop.color = (float(stop['colorR']),float(stop['colorG']),float(stop['colorB']),float(stop['alpha']))

        prevRightColor = (float(stop['colorR']),float(stop['colorG']),float(stop['colorB']),float(stop['alpha']))
        
        if stop['midpointCoordinate'] > -1:
            #print('mid stop: '+str((float(stop['midpointCoordinate'])-float(row['leftEndpointCoordinate']))/float(stopsRange)))
            midStopPos = (float(stop['midpointCoordinate'])-float(row['leftEndpointCoordinate']))/float(stopsRange)
            midStopTempPos = ((float(stop['leftEndpointCoordinate'])+((float(stop['rightEndpointCoordinate'])-float(stop['leftEndpointCoordinate']))/2.0))-float(row['leftEndpointCoordinate']))/float(stopsRange)
            midStop = node.color_ramp.elements.new(1)
            if coloringType == 'HSV':
                firstStopHsv = rgb2hsv((float(stop['prevColorR']),float(stop['prevColorG']),float(stop['prevColorB']),float(stop['prevAlpha'])))
                if firstStopHsv[0] == 1:
                    firstStopHsv[0] = 0

                secondStopHsv = rgb2hsv((float(stop['colorR']),float(stop['colorG']),float(stop['colorB']),float(stop['alpha'])))
                if secondStopHsv[0] == 0:
                    secondStopHsv[0] = 1
                if hueInterpolation == 'CCW':
                    midStopHsv = (
                        (firstStopHsv[0]+secondStopHsv[0])/2.0,
                        (firstStopHsv[1]+secondStopHsv[1])/2.0,
                        (firstStopHsv[2]+secondStopHsv[2])/2.0,
                        (firstStopHsv[3]+secondStopHsv[3])/2.0,
                        )
                    #print(str(midStopHsv))

                else:
                    midStopHsv = (
                        (abs(secondStopHsv[0]-firstStopHsv[0]))/2.0,
                        (firstStopHsv[1]+secondStopHsv[1])/2.0,
                        (firstStopHsv[2]+secondStopHsv[2])/2.0,
                        (firstStopHsv[3]+secondStopHsv[3])/2.0,
                        )                   
                midStop.color = hsv2rgb(midStopHsv)
            midStop.position = midStopPos
    node.color_ramp.color_mode = coloringType
          
        
    return

def hsv2rgb(colIn):
    import colorsys
    colOutRGB = colorsys.hsv_to_rgb(colIn[0],colIn[1],colIn[2])
    colOut = [colOutRGB[0],colOutRGB[1],colOutRGB[2],colIn[3]]
    #print(str(colOut))
    return colOut


def rgb2hsv(colIn):
    import colorsys
    colOutRGB = colorsys.rgb_to_hsv(colIn[0],colIn[1],colIn[2])
    colOut = [colOutRGB[0],colOutRGB[1],colOutRGB[2],colIn[3]]
    #print(str(colOut))
    return colOut

def hex_to_rgb(value):
    value = value.lstrip('#')
    lv = len(value)
    return list(float(int(value[i:i + lv // 3], 16))/255 for i in range(0, lv, lv // 3))

cssColors = {
        'black':hex_to_rgb('#000000'),      #000000	0,0,0
        'silver':hex_to_rgb('#C0C0C0'),	    #C0C0C0	192,192,192
        'gray':hex_to_rgb('#808080'),	    #808080	128,128,128
        'white':hex_to_rgb('#FFFFFF'),	    #FFFFFF	255,255,255
        'maroon':hex_to_rgb('#800000'),	    #800000	128,0,0
        'red':hex_to_rgb('#FF0000'),	    #FF0000	255,0,0
        'purple':hex_to_rgb('#800080'),     #800080	128,0,128
        'fuchsia':hex_to_rgb('#FF00FF'),    #FF00FF	255,0,255
        'green':hex_to_rgb('#008000'),	    #008000	0,128,0
        'lime':hex_to_rgb('#00FF00'),	    #00FF00	0,255,0
        'olive':hex_to_rgb('#808000'),	    #808000	128,128,0
        'yellow':hex_to_rgb('#FFFF00'),	    #FFFF00	255,255,0
        'navy':hex_to_rgb('#000080'),	    #000080	0,0,128
        'blue':hex_to_rgb('#0000FF'),	    #0000FF	0,0,255
        'teal':hex_to_rgb('#008080'),	    #008080	0,128,128
        'aqua':hex_to_rgb('#00FFFF'),	    #00FFFF	0,255,255
        }


def clearColorRamp(node):
    while len(node.color_ramp.elements)>1:
        node.color_ramp.elements.remove(node.color_ramp.elements[1])
    firstElement = node.color_ramp.elements[0]
    firstElement.color = (1,1,1,1)
    firstElement.position = 0.0
    return

def compressGradientData(gradientDataIn):
    n = 0
    currStops = []
    output = []
    currStopsCount = 0
    gradientDataOut = []
    #print(str(gradientDataIn))
    for row in gradientDataIn:
        n += 1
        #if midpoint coordinate is important add two stops to counter, else add one
        if row['midpointCoordinate'] != -1:
            currStopsCount += 2
        else:
            currStopsCount += 1
        if len(currStops) > 0:
            currLeftColor = (row['prevColorR'],row['prevColorG'],row['prevColorB'],row['prevAlpha'])
            if currLeftColor != prevRightColor:
                #print("Different stops at one position?")
                #print(str(currRightColor))
                #print(str(prevRightColor))
                #print("")
                currStopsCount += 1

        prevRightColor = (row['colorR'],row['colorG'],row['colorB'],row['alpha'])
        
        if len(currStops) == 0:
            currStops.append(
                {
                    'leftEndpointCoordinate':row['leftEndpointCoordinate'],
                    'midpointCoordinate':row['midpointCoordinate'],
                    'rightEndpointCoordinate':row['rightEndpointCoordinate'],
                    'prevColorR':row['prevColorR'],
                    'prevColorG':row['prevColorG'],
                    'prevColorB':row['prevColorB'],
                    'colorR':row['colorR'],
                    'colorG':row['colorG'],
                    'colorB':row['colorB'],
                    'prevAlpha':row['prevAlpha'],
                    'alpha':row['alpha'],
                              }
                )
            currLeftEndpointCoordinate = row['leftEndpointCoordinate']
            currRightEndpointCoordinate = row['rightEndpointCoordinate']
            currInterpolation = row['interpolation']
            currColoringType = row['coloringType']
            currStopsCount += 1 # add one stop to counter when the stop is the first in the package
            
        else:
            if currStopsCount > 32 or row['interpolation'] != currInterpolation or row['coloringType'] != currColoringType:
                gradientDataOut.append({'stops':currStops[:],
                        'interpolation':currInterpolation,
                        'coloringType':currColoringType,
                        'leftEndpointCoordinate':currLeftEndpointCoordinate,
                        'rightEndpointCoordinate':currRightEndpointCoordinate,
                    })

                if row['midpointCoordinate'] != -1:
                    currStopsCount = 3
                else:
                    currStopsCount = 2
                currStops = []
                
                currStops.append(
                    {
                        'leftEndpointCoordinate':row['leftEndpointCoordinate'],
                        'midpointCoordinate':row['midpointCoordinate'],
                        'rightEndpointCoordinate':row['rightEndpointCoordinate'],
                        'prevColorR':row['prevColorR'],
                        'prevColorG':row['prevColorG'],
                        'prevColorB':row['prevColorB'],
                        'colorR':row['colorR'],
                        'colorG':row['colorG'],
                        'colorB':row['colorB'],
                        'prevAlpha':row['prevAlpha'],
                        'alpha':row['alpha'],
                                  }
                    )
                currLeftEndpointCoordinate = row['leftEndpointCoordinate']
                currRightEndpointCoordinate = row['rightEndpointCoordinate']
                currInterpolation = row['interpolation']
                currColoringType = row['coloringType']
            else:
                currStops.append(
                    {
                        'leftEndpointCoordinate':row['leftEndpointCoordinate'],
                        'midpointCoordinate':row['midpointCoordinate'],
                        'rightEndpointCoordinate':row['rightEndpointCoordinate'],
                        'prevColorR':row['prevColorR'],
                        'prevColorG':row['prevColorG'],
                        'prevColorB':row['prevColorB'],
                        'colorR':row['colorR'],
                        'colorG':row['colorG'],
                        'colorB':row['colorB'],
                        'prevAlpha':row['prevAlpha'],
                        'alpha':row['alpha'],
                                  }
                    )
                currRightEndpointCoordinate = row['rightEndpointCoordinate']

        if n == len(gradientDataIn):
            gradientDataOut.append({'stops':currStops,
                 'interpolation':currInterpolation,
                 'coloringType':currColoringType,
                'leftEndpointCoordinate':currLeftEndpointCoordinate,
                'rightEndpointCoordinate':currRightEndpointCoordinate,
            })
            return gradientDataOut               


def getLinks(node_tree,node_name,deleteOld=False):
    linksIn = []
    linksOut = []
    
    for link in node_tree.links:
        
        if link.from_node.name==node_name:
            linksOut.append({"to_node":
                            {"name":link.to_node.name,
                             "socket":int(link.to_socket.path_from_id()[-2:-1])},
                            "socket":int(link.from_socket.path_from_id()[-2:-1])
                             }
                            )
            if deleteOld:
                node_tree.links.remove(link)
            
        elif link.to_node.name==node_name:
            linksIn.append({"from_node":
                            {"name":link.from_node.name,
                             "socket":int(link.from_socket.path_from_id()[-2:-1])},
                            "socket":int(link.to_socket.path_from_id()[-2:-1])
                             }
                            )
            if deleteOld:
                node_tree.links.remove(link)
                
    return {'linksIn':linksIn,'linksOut':linksOut}

def setLinks(node_tree,node_name,links):
    for li in links['linksIn']:
        node_tree.links.new(
            node_tree.nodes[li["from_node"]["name"]].outputs[li["from_node"]["socket"]],
            node_tree.nodes[node_name].inputs[li["socket"]]
            )
    for lo in links['linksOut']:
        node_tree.links.new(
            node_tree.nodes[node_name].outputs[lo["socket"]],
            node_tree.nodes[lo["to_node"]["name"]].inputs[lo["to_node"]["socket"]]
            )
        
def deleteLinks(node_tree,links):
    for l in links['linksIn']:
        try:
            node_tree.links.remove(l)
        except:
            pass
    for l in links['linksOut']:
        try:
            node_tree.links.remove(l)
        except:
            pass



class ImportToNode(Operator):
    """Mixin class to be inherited by classes for importing particular formats"""
    #import_function = None
    #import_function_args = ['filepath','use_alpha']
    #import_format = 'txt'
    
    #engines_supported = ['CYCLES','BLENDER_GAME','BLENDER_RENDER']
    #trees_supported = ['ShaderNodeTree','CompositorNodeTree','TextureNodeTree']
    #alpha_supported = False




    def execute(self, context):
        #return read_svg(context, self.filepath,self.interpolation)

        #print(40*'#')
        #print(dir(self))
        #print(40*'#')
        
        filepath = self.filepath
        print(filepath)
        gradientName = os.path.basename(filepath)
        if '.' in gradientName:
            gradientName = gradientName.rpartition('.')[0]
        #interpolation = self.interpolation
        if not self.alpha_supported:
            self.use_alpha = None
        use_alpha = self.use_alpha
        
        replaceColorRampWithGroup = self.replace_with_group        
        
        #get active node
        space = context.space_data
        node_tree = space.node_tree
        node_tree_type = space.tree_type
        node_active = context.active_node    
                 
        node_active_loc = node_active.location
        node_active_name = node_active.name

        #gradientData = import_function(filepath,use_alpha)
        #print([getattr(self,att) for att in self.import_function_args])
        import_function = globals()[self.import_function]
        gradientData = import_function(*[getattr(self,att) for att in self.import_function_args])
        #gradientData = import_function(self.filepath,self.use_alpha)
        gradientData = compressGradientData(gradientData)
        #newGroup = groupFromGradient(gradientData,gradientName)
        #newGroupName = groupFromGradient(gradientData,gradientName,node_tree_type,node_tree)
        
        if len(gradientData) > 0:
            #gradientData = compressGradientData(gradientData)
            if len(gradientData) > 1:
                if replaceColorRampWithGroup:
                    newGroupName = groupFromGradient(gradientData,gradientName,node_tree_type,node_tree,alpha_supported=self.alpha_supported)
                    
                    node_active_loc = node_active.location
                    node_active_name = node_active.name
                    #get old node links
                    links = getLinks(node_tree,node_active_name)
                    #set/restore links
                    setLinks(node_tree,newGroupName,links)
                    #remove node                                 
                    node_tree.nodes.remove(node_tree.nodes[node_active_name])
                    #clean up old links
                    deleteLinks(node_tree,links)
                    #set location                
                    node_tree.nodes[newGroupName].location = node_active_loc
                    
                    return {'FINISHED'}
                else:
                    msg = "More than 32 color stops found in {extension} file. Due to Blender's limitation the maximum number of 32 color stops can be added to single ColorRamp. Terminating import process. Large gradients can be imported when option 'Replace ColorRamp with node group if needed' is selected.".format(extension=import_format)
                    print(msg)
                    self.report({'ERROR'}, msg)
                    return {'FINISHED'}                                    
            else:
                setColorStops(node_active,gradientData[0])
                return {'FINISHED'}
        else:
            msg = "No gradient could be read from {extension} file.".format(extension=import_format)
            print(msg)
            self.report({'ERROR'}, msg)            
            return {'FINISHED'}

    @classmethod  
    def poll(cls, context):
        engine = context.scene.render.engine in cls.engines_supported
        if nw_check(context):
            space = context.space_data
            #print(space.tree_type)
            if space.tree_type in cls.trees_supported and engine:
                if context.active_node:
                    if context.active_node.type == "VALTORGB":
                        #print(context.active_node.type)
                        return True

        return False


#svg import classes
#class for importing to ShaderNodeTree and CompositorNodeTree
    
class ImportSVGToNode(ImportToNode,ImportHelper):
    """Import svg file to active color ramp node"""
    bl_idname = "import.svg_as_color_ramp"  
    bl_label = "Import svg file to active color ramp node"
    
    import_function = 'svg2gradient'
    import_function_args = ['filepath','use_alpha']
    import_format = 'svg'
    
    engines_supported = ['CYCLES','BLENDER_GAME','BLENDER_RENDER']
    trees_supported = ['ShaderNodeTree','CompositorNodeTree']
    alpha_supported = True

    # ImportHelper mixin class uses this
    filename_ext = "."+import_format

    filter_glob = StringProperty(
            default="*."+import_format,
            options={'HIDDEN'},
            )

    if alpha_supported:
        use_alpha = BoolProperty(
                name="Use {extension} aplha values".format(extension=import_format.upper()),
                description="Decides whether alpha values of color stops should be taken from {extension} file or used as default (1)".format(extension=import_format),
                default=True,
                )

    replace_with_group = BoolProperty(
            name="Replace ColorRamp with node group if needed",
            description="Decides whether big linear gradients (more than 32 color stops) should be replaced with new node group.",
            default=True,
            )


    interpolation = EnumProperty(
            name="Interpolation method",
            description="Choose between available interpolation methods",
            items=(
                   ('CONSTANT', "Constant", "Constant interpolation"),
                   ('B_SPLINE', "B-Spline", "B-Spline interpolation"),
                   ('LINEAR', "Linear", "Linear interpolation"),
                   ('CARDINAL', "Cardinal", "Cardinal interpolation"),
                   ('EASE', "Ease", "Ease interpolation")
                   ),
            default='LINEAR',
            )
#class for importing to TextureNodeTree
    
class ImportSVGToTextureNode(ImportToNode,ImportHelper):
    """Import svg file to active color ramp node - tex"""
    bl_idname = "import.svg_as_color_ramp_tex"  
    bl_label = "Import svg file to active color ramp node - tex"

    import_function = 'svg2gradient'
    import_function_args = ['filepath','use_alpha']
    import_format = 'svg'

    engines_supported = ['CYCLES','BLENDER_GAME','BLENDER_RENDER']
    trees_supported = ['TextureNodeTree']
    alpha_supported = False

    # ImportHelper mixin class uses this
    filename_ext = "."+import_format

    filter_glob = StringProperty(
            default="*."+import_format,
            options={'HIDDEN'},
            )

    if alpha_supported:
        use_alpha = BoolProperty(
                name="Use {extension} aplha values".format(extension=import_format.upper()),
                description="Decides whether alpha values of color stops should be taken from {extension} file or used as default (1)".format(extension=import_format),
                default=True,
                )

    replace_with_group = BoolProperty(
            name="Replace ColorRamp with node group if needed",
            description="Decides whether big linear gradients (more than 32 color stops) should be replaced with new node group.",
            default=True,
            )


    interpolation = EnumProperty(
            name="Interpolation method",
            description="Choose between available interpolation methods",
            items=(
                   ('CONSTANT', "Constant", "Constant interpolation"),
                   ('B_SPLINE', "B-Spline", "B-Spline interpolation"),
                   ('LINEAR', "Linear", "Linear interpolation"),
                   ('CARDINAL', "Cardinal", "Cardinal interpolation"),
                   ('EASE', "Ease", "Ease interpolation")
                   ),
            default='LINEAR',
            )

#ggr import classes
#class for importing to ShaderNodeTree and CompositorNodeTree

class ImportGGRToNode(ImportToNode,ImportHelper):
    """Import ggr file to active color ramp node"""
    bl_idname = "import.ggr_as_color_ramp"  
    bl_label = "Import ggr file to active color ramp node"
    import_function = 'ggr2gradient'
    import_function_args = ['filepath','use_alpha','color_fg','color_bg']
    import_format = 'ggr'
    
    engines_supported = ['CYCLES','BLENDER_GAME','BLENDER_RENDER']
    trees_supported = ['ShaderNodeTree','CompositorNodeTree']
    alpha_supported = True

    # ImportHelper mixin class uses this
    filename_ext = "."+import_format

    filter_glob = StringProperty(
            default="*."+import_format,
            options={'HIDDEN'},
            )

    if alpha_supported:
        use_alpha = BoolProperty(
                name="Use {extension} aplha values".format(extension=import_format.upper()),
                description="Decides whether alpha values of color stops should be taken from {extension} file or used as default (1)".format(extension=import_format),
                default=True,
                )

    replace_with_group = BoolProperty(
            name="Replace ColorRamp with node group if needed",
            description="Decides whether big linear gradients (more than 32 color stops) should be replaced with new node group.",
            default=True,
            )

    color_fg = FloatVectorProperty(
                 name = "Foreground color",
                 subtype = "COLOR",
                 size = 4,
                 min = 0.0,
                 max = 1.0,
                 default = (0.0,0.0,0.0,1.0),
                 description="Foreground color used for ggr color stops which are defined as having foreground color.",
                 ) 
    color_bg = FloatVectorProperty(
                 name = "Background color",
                 subtype = "COLOR",
                 size = 4,
                 min = 0.0,
                 max = 1.0,
                 default = (1.0,1.0,1.0,1.0),
                 description="Background color used for ggr color stops which are defined as having background color.",
                 )
    
#class for importing to TextureNodeTree    
class ImportGGRToTextureNode(ImportToNode,ImportHelper):
    """Import ggr file to active color ramp node - tex"""
    bl_idname = "import.ggr_as_color_ramp_tex"  
    bl_label = "Import ggr file to active color ramp node - tex"
    
    import_function = 'ggr2gradient'
    import_function_args = ['filepath','use_alpha','color_fg','color_bg']
    import_format = 'ggr'

    engines_supported = ['CYCLES','BLENDER_GAME','BLENDER_RENDER']
    trees_supported = ['TextureNodeTree']
    alpha_supported = False

    # ImportHelper mixin class uses this
    filename_ext = "."+import_format

    filter_glob = StringProperty(
            default="*."+import_format,
            options={'HIDDEN'},
            )

    if alpha_supported:
        use_alpha = BoolProperty(
                name="Use {extension} aplha values".format(extension=import_format.upper()),
                description="Decides whether alpha values of color stops should be taken from {extension} file or used as default (1)".format(extension=import_format),
                default=True,
                )

    replace_with_group = BoolProperty(
            name="Replace ColorRamp with node group if needed",
            description="Decides whether big linear gradients (more than 32 color stops) should be replaced with new node group.",
            default=True,
            )

    color_fg = FloatVectorProperty(
                 name = "Foreground color",
                 subtype = "COLOR",
                 size = 4,
                 min = 0.0,
                 max = 1.0,
                 default = (0.0,0.0,0.0,1.0),
                 description="Foreground color used for ggr color stops which are defined as having foreground color.",
                 ) 
    color_bg = FloatVectorProperty(
                 name = "Background color",
                 subtype = "COLOR",
                 size = 4,
                 min = 0.0,
                 max = 1.0,
                 default = (1.0,1.0,1.0,1.0),
                 description="Background color used for ggr color stops which are defined as having background color.",
                 )

#css import classes
#class for importing to ShaderNodeTree and CompositorNodeTree
    
class ImportCSSToNode(ImportToNode,ImportHelper):
    """Import css file to active color ramp node"""
    bl_idname = "import.css_as_color_ramp"  
    bl_label = "Import css file to active color ramp node"
    import_function = 'css2gradient'
    import_function_args = ['filepath','use_alpha']
    import_format = 'css'
    
    engines_supported = ['CYCLES','BLENDER_GAME','BLENDER_RENDER']
    trees_supported = ['ShaderNodeTree','CompositorNodeTree']
    alpha_supported = True

    # ImportHelper mixin class uses this
    filename_ext = "."+import_format

    filter_glob = StringProperty(
            default="*."+import_format,
            options={'HIDDEN'},
            )

    if alpha_supported:
        use_alpha = BoolProperty(
                name="Use {extension} aplha values".format(extension=import_format.upper()),
                description="Decides whether alpha values of color stops should be taken from {extension} file or used as default (1)".format(extension=import_format),
                default=True,
                )

    replace_with_group = BoolProperty(
            name="Replace ColorRamp with node group if needed",
            description="Decides whether big linear gradients (more than 32 color stops) should be replaced with new node group.",
            default=True,
            )

#class for importing to TextureNodeTree

class ImportCSSToTextureNode(ImportToNode,ImportHelper):
    """Import css file to active color ramp node - tex"""
    bl_idname = "import.css_as_color_ramp_tex"  
    bl_label = "Import css file to active color ramp node - tex"

    import_function = 'css2gradient'
    import_function_args = ['filepath','use_alpha']
    import_format = 'css'

    engines_supported = ['CYCLES','BLENDER_GAME','BLENDER_RENDER']
    trees_supported = ['TextureNodeTree']
    alpha_supported = False

    # ImportHelper mixin class uses this
    filename_ext = "."+import_format

    filter_glob = StringProperty(
            default="*."+import_format,
            options={'HIDDEN'},
            )

    if alpha_supported:
        use_alpha = BoolProperty(
                name="Use {extension} aplha values".format(extension=import_format.upper()),
                description="Decides whether alpha values of color stops should be taken from {extension} file or used as default (1)".format(extension=import_format),
                default=True,
                )

    replace_with_group = BoolProperty(
            name="Replace ColorRamp with node group if needed",
            description="Decides whether big linear gradients (more than 32 color stops) should be replaced with new node group.",
            default=True,
            )



class gradientFromImage(Operator):
    """Scans an image loaded to UV/Image Editor and generates gradient for an active ColorRampNode"""
    bl_idname = "image.gradient_from_image"  
    bl_label = "Scan gradient"


    replace_with_group = BoolProperty(
            name="Replace ColorRamp with node group if needed",
            description="Decides whether big linear gradients (more than 32 color stops) should be replaced with new node group.",
            default=False,
            )

##    colorStopsCount = FloatVectorProperty(
##                 name = "Number of color stops",
##                 subtype = "NONE",
##                 size = 1,
##                 min = 2.0,
##                 max = 512.0,
##                 step = 1.0,
##                 default = (32.0,),
##                 precision = 0,
##                 description="Number of color stops for the scanned gradient",
##                 )

    use_alpha = BoolProperty(
            name="Use image aplha values",
            description="Decides whether alpha values of color stops should be taken from image or used as default value of 1.0",
            default=True,
            )
    
    colorStopsCount = IntProperty(
                 name = "Number of color stops",
                 subtype = "NONE",
                 #size = 1,
                 min = 2,
                 max = 512,
                 step = 1,
                 default =  32,
                 #precision = 0,
                 description="Number of color stops for the scanned gradient",
                 ) 


    gpStrokeType = EnumProperty(
            name="Grease pencil part",
            description="Which grease pencil elements should be considered when scanning image to acquire gradient",
            items=(
                   ('LAYER', "Layer", "All the strokes from the active layer"),
                   ('STROKE', "Stroke", "Last stroke of the active layer"),
                   ('2POINTS', "Last 2 points", "Last two points of the last stroke of the active layer"),
                   ),
            default='STROKE',
            )

    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self)

    def execute(self, context):

        useAlpha = self.use_alpha
        
        node_tree = bpy.context.active_object.active_material.node_tree
        node_active = node_tree.nodes.active

        node_tree_type = {'SHADER':'ShaderNodeTree','COMPOSITING':'CompositorNodeTree','TEXTURE':'TextureNodeTree'}.get(node_tree.type)
        
        #print(node_active.name)

        colorStopsCount = self.colorStopsCount

        replaceColorRampWithGroup = self.replace_with_group
        
        activeImage = ''
        gpStrokeType = self.gpStrokeType #last 2 points, last stroke, whole layer

        gp = bpy.context.area.spaces[0].grease_pencil
        
        gp_active_layer = gp.layers.active
        
        if gpStrokeType == 'LAYER':
            #gpencil_points = [point.co for stroke.points in stroke for stroke in gp.layers[-1].strokes]
            gpencil_points = [[point.co for point in stroke.points] for stroke in gp_active_layer.active_frame.strokes]
        elif gpStrokeType == 'STROKE':
            gpencil_points = [[point.co for point in gp_active_layer.active_frame.strokes[-1].points]]
        elif gpStrokeType == '2POINTS':
            if len(gp_active_layer.active_frame.strokes[-1].points) < 2:
                msg = "Last stroke is not drawn or it has only one point."
                print(msg)
                self.report({'ERROR'}, msg)            
                return {'FINISHED'}
            else:
                gpencil_points = [[
                gp_active_layer.active_frame.strokes[-1].points[-2].co,
                gp_active_layer.active_frame.strokes[-1].points[-1].co,
                ]]
        else:
            gpencil_points = []
        #print(str(gpencil_points))
        #print(str(len(gpencil_points)))

        if len(gpencil_points[-1]) < 2:
            msg = "Selected grease pencil element (eg. stroke, layer) should have at least 2 points."
            print(msg)
            self.report({'ERROR'}, msg)            
            return {'FINISHED'}            

        rasterPoints = getPoints(gpencil_points,colorStopsCount)
        #print("")
        #print(str(rasterPoints))
        #raster = bpy.data.screens['UV Editing'].areas[1].spaces[0].image
        for area in context.screen.areas:
            if area.type == 'IMAGE_EDITOR':
                raster = area.spaces.active.image
        colors = pixelColors(rasterPoints,raster)
        #print(str(colors))
    
        gradientData = []
        #print(str(stops))
        n = 0
        for color in colors:
            
            alpha = 1.0
            if useAlpha:
                if len(color) == 4:
                    alpha = color[3]
            if n != 0:
                rightEndpointCoordinate = float(n/len(colors))
                gradientData.append(
                    {
                        'leftEndpointCoordinate':prevRightEndpointCoordinate,
                        'midpointCoordinate':-1,
                        'rightEndpointCoordinate':rightEndpointCoordinate,
                        'prevColorR':prevColorR,
                        'prevColorG':prevColorG,
                        'prevColorB':prevColorB,
                        'prevAlpha':prevAlpha,
                        'colorR':color[0],
                        'colorG':color[1],
                        'colorB':color[2],
                        'alpha':alpha,
                        'interpolation':0,
                        'coloringType':0,
                     }
                    )
                prevColorR = color[0]
                prevColorG = color[1]
                prevColorB = color[2]
                prevRightEndpointCoordinate = rightEndpointCoordinate
                prevAlpha = alpha
            else:
                if len(colors) == 1:
                    gradientData.append(
                        {
                            'leftEndpointCoordinate':0.0,
                            'midpointCoordinate':-1,
                            'rightEndpointCoordinate':1.0,
                            'prevColorR':color[0],
                            'prevColorG':color[1],
                            'prevColorB':color[2],
                            'prevAlpha':alpha,
                            'colorR':color[0],
                            'colorG':color[1],
                            'colorB':color[2],
                            'alpha':alpha,
                            'interpolation':0,
                            'coloringType':0,
                         }
                        )                

                else:            
                    prevColorR = color[0]
                    prevColorG = color[1]
                    prevColorB = color[2]
                    prevAlpha = alpha
                    prevRightEndpointCoordinate = 0.0            
        
            n += 1
        gradientData = compressGradientData(gradientData)
        if len(gradientData) > 0:
            #gradientData = compressGradientData(gradientData)
            if len(gradientData) > 1:
                if replaceColorRampWithGroup:
                    gradientName = raster.name

                    if node_tree_type == 'TextureNodeTree':
                        alpha_supported = False
                    else:
                        alpha_supported = True
                    
                    newGroupName = groupFromGradient(gradientData,gradientName,node_tree_type,node_tree,alpha_supported=alpha_supported)
                    
                    node_active_loc = node_active.location
                    node_active_name = node_active.name
                    #get old node links
                    links = getLinks(node_tree,node_active_name)
                    #set/restore links
                    setLinks(node_tree,newGroupName,links)
                    #remove node                                 
                    node_tree.nodes.remove(node_tree.nodes[node_active_name])
                    #clean up old links
                    deleteLinks(node_tree,links)
                    #set location                
                    node_tree.nodes[newGroupName].location = node_active_loc
                    
                    return {'FINISHED'}
                else:
                    msg = "More than 32 color stops found in the image. Due to Blender's limitation the maximum number of 32 color stops can be added to single ColorRamp. Terminating process. Large gradients can be imported when option 'Replace ColorRamp with node group if needed' is selected."
                    print(msg)
                    self.report({'ERROR'}, msg)
                    return {'FINISHED'}                                    
            else:
                setColorStops(node_active,gradientData[0])
                return {'FINISHED'}
        else:
            msg = "No gradient could be read from the image."
            print(msg)
            self.report({'ERROR'}, msg)            
            return {'FINISHED'}

               
                    
   
    @classmethod  
    def poll(cls, context):
        #return True
        engine = context.scene.render.engine in ['CYCLES','BLENDER_GAME','BLENDER_RENDER']
        if engine:
            node_tree = bpy.context.active_object.active_material.node_tree
            print(node_tree.type)
            if node_tree:
                node_active = node_tree.nodes.active
                node_tree_type = {'SHADER':'ShaderNodeTree','COMPOSITING':'CompositorNodeTree','TEXTURE':'TextureNodeTree'}.get(node_tree.type)

                raster = None
                for area in context.screen.areas:
                    if area.type == 'IMAGE_EDITOR':
                        raster = area.spaces.active.image

                if raster:        
                    space = context.space_data
                    #if space.tree_type in ['ShaderNodeTree','CompositorNodeTree'] and engine:
                    if space.type == 'IMAGE_EDITOR' and node_tree_type in ['ShaderNodeTree','CompositorNodeTree','TextureNodeTree']:
                        if node_active:
                            if node_active.type == "VALTORGB":
                                #print(context.active_node.type)
                                return True
        return False

def polylineLength(polyline):
    length = 0
    for i in range(0,len(polyline)-1):
        length+=lineLength(polyline[i],polyline[i+1])
    return length
    
def lineLength(firstPoint,secondPoint):
    return (firstPoint - secondPoint).length

def getPoints(polyline,pointCount):
    #returns list of points coordinates on a multipart polyline based on its length and number of requested points
    
    #temp
    #pointCount = 2
    
    total_length = 0
    for i in range(0,len(polyline)):
        part = polyline[i]
        partLength = polylineLength(part)
        total_length += partLength
        print("Part: "+str(i))
        print("Points: "+str(len(part)))
        print("Length: "+str(partLength))
        print(" ")
    segment_length = total_length/(pointCount-1)
    
    print("Total Length: "+str(total_length))
    print("Segment Length: "+str(segment_length))
    print("Segments: "+str(pointCount))
    print(" ")
    points = []
    
    for i in range(0,pointCount):
        if i == 0:
            points.append( (polyline[0][0].x, polyline[0][0].y) )
        elif i == (pointCount-1):
            points.append( (polyline[-1][-1].x, polyline[-1][-1].y) )
        else:
            points.append(getPoint(polyline,i*segment_length))
    return points

def getPoint(polyline,distance):
    #returns coordinates of a point at a specyfic distance along multipart polyline
    total_length=0
    for part in polyline:
        partLength = polylineLength(part)
        if total_length + partLength < distance:
            total_length += partLength
        else:
            distance_along_part = distance - total_length
            if len(part) == 2:
                print("Total length: "+str(total_length))
                print("Dist. along part: "+str(distance_along_part))
                print("Part length: "+str(partLength))
                #return sqrt( (( part[1].x - part[0].x )*( part[1].x - part[0].x ))+(( part[1].y-part[0].y )*( part[1].y-part[0].y )) )
                difference = part[1]-part[0]
                difference.normalize()
                vect = distance_along_part*difference
                #print("Difference length: "+str((part[1]-part[0]).length))
                print("Vector length: "+str(vect.length))
                return (part[0].x + vect.x, part[0].y + vect.y)
            else:
                return getPoint([[part[i],part[i+1]] for i in range(0,len(part)-1)],distance_along_part)

def pixelColors(points,raster):
    width = raster.size[0]
    height = raster.size[1]
    channels = raster.channels
    colors = []
    for p in points:
        color = []
        col = int(width*p[0])
        row = int(height*p[1])
        print(str(row))
        print(str(col))
        for channelOffset in range(0,channels):
            color.append(raster.pixels[ channels * ( col + width * row ) + channelOffset ] )
        for i in range(0,4-channels):
            color.append(1.0)
        
        colors.append(color[:])
    return colors
    
class gradientFromImagePanel(bpy.types.Panel):
    """Creates a Panel nodes ui window"""
    bl_idname = "SCAN_IMAGE_TO_NODE_COLORRAMP"
    bl_space_type = 'IMAGE_EDITOR'
    bl_region_type = 'UI'
    bl_label = "Color ramp"

    
    
    def draw(self, context):
        layout = self.layout

        row = layout.row()
        #row.operator("import.gradientFromImage", text="Scan gradient to active color ramp")
        row.operator(gradientFromImage.bl_idname, text="Scan gradient to active color ramp")
        #row = layout.row()
        #row.prop(gradientFromImage, "replace_with_group")
        #row = layout.row()
        #row.prop(gradientFromImage, "colorStopsCount")
        #row = layout.row()
        #row.prop("image.gradient_from_image", "gpStrokeType")
      

class ImportGradientToNodePanel(bpy.types.Panel):
    """Creates a Panel nodes ui window"""
    bl_idname = "NODE_COLORRAMP_IMPORT"
    bl_space_type = 'NODE_EDITOR'
    bl_region_type = 'UI'
    bl_label = "Color ramp"

    
    
    def draw(self, context):
        layout = self.layout
        if context.space_data.tree_type == 'TextureNodeTree':
            suffix = '_tex'
        else:
            suffix = ''
        row = layout.row()
        row.operator("import.svg_as_color_ramp"+suffix, text="Import SVG")
        row = layout.row()
        row.operator("import.ggr_as_color_ramp"+suffix, text="Import GGR")
        row = layout.row()
        row.operator("import.css_as_color_ramp"+suffix, text="Import CSS")

    
def menu_func_import(self, context):
    self.layout.operator(ImportSVGToNode.bl_idname, text="Import svg file to active color ramp node")
    self.layout.operator(ImportGGRToNode.bl_idname, text="Import ggr file to active color ramp node")
    self.layout.operator(ImportCSSToNode.bl_idname, text="Import css file to active color ramp node")
    self.layout.operator(ImportSVGToTextureNode.bl_idname, text="Import svg file to active color ramp node - tex")
    self.layout.operator(ImportGGRToTextureNode.bl_idname, text="Import ggr file to active color ramp node - tex")
    self.layout.operator(ImportCSSToTextureNode.bl_idname, text="Import css file to active color ramp node - tex")
    self.layout.operator(gradientFromImage.bl_idname, text="Scan gradient from image to active color ramp node")



def register():
    #bpy.utils.register_class(ImportToNode)
    bpy.utils.register_class(ImportSVGToNode)
    bpy.utils.register_class(ImportSVGToTextureNode)
    bpy.utils.register_class(ImportGGRToNode)
    bpy.utils.register_class(ImportGGRToTextureNode)
    bpy.utils.register_class(ImportCSSToNode)
    bpy.utils.register_class(ImportCSSToTextureNode)
    bpy.utils.register_class(gradientFromImage)
    bpy.utils.register_class(ImportGradientToNodePanel)
    bpy.utils.register_class(gradientFromImagePanel)
    bpy.types.NODE_MT_node.append(menu_func_import)


def unregister():
    #bpy.utils.unregister_class(ImportToNode)
    bpy.utils.unregister_class(ImportSVGToNode)
    bpy.utils.unregister_class(ImportSVGToTextureNode)
    bpy.utils.unregister_class(ImportGGRToNode)
    bpy.utils.unregister_class(ImportGGRToTextureNode)
    bpy.utils.unregister_class(ImportCSSToNode)
    bpy.utils.unregister_class(ImportCSSToTextureNode)
    bpy.utils.unregister_class(gradientFromImage)
    bpy.utils.unregister_class(ImportGradientToNodePanel)
    bpy.utils.unregister_class(gradientFromImagePanel)
    bpy.types.NODE_MT_node.remove(menu_func_import)

if __name__ == "__main__":
    register()

