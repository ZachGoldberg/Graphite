"""Copyright 2008 Orbitz WorldWide

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

   http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License."""

import os, cairo, math, itertools
from time import strftime, localtime, timezone, altzone, daylight, tzset, mktime
from calendar import timegm
from urllib import unquote_plus
from ConfigParser import SafeConfigParser
from django.conf import settings

colorAliases = {
  'black' : (0,0,0),
  'white' : (255,255,255),
  'blue' : (100,100,255),
  'green' : (0,200,0),
  'red' : (200,00,50),
  'yellow' : (255,255,0),
  'purple' : (200,100,255),
  'brown' : (150,100,50),
  'aqua' : (0,150,150),
  'gray' : (175,175,175),
  'grey' : (175,175,175),
  'magenta' : (255,0,255),
  'pink' : (255,100,100),
  'gold' : (200,200,0),
  'rose' : (200,150,200),
  'darkblue' : (0,0,255),
  'darkgreen' : (0,255,0),
  'darkred' : (255,0,0),
  'darkgray' : (111,111,111),
  'darkgrey' : (111,111,111),
}

#X-axis configurations (copied from rrdtool, this technique is evil & ugly but effective)
SEC = 1
MIN = 60
HOUR = MIN * 60
DAY = HOUR * 24
WEEK = DAY * 7
MONTH = DAY * 30
YEAR = DAY * 365
xAxisConfigs = (
  dict(seconds=0.00,  minorGridUnit=SEC,  minorGridStep=10, majorGridUnit=MIN,  majorGridStep=1,  labelUnit=SEC,  labelStep=10, format="%H:%M:%S"),
  dict(seconds=0.04,  minorGridUnit=SEC,  minorGridStep=5,  majorGridUnit=MIN,  majorGridStep=1,  labelUnit=SEC,  labelStep=5,  format="%H:%M:%S"),
  dict(seconds=0.07,  minorGridUnit=SEC,  minorGridStep=15, majorGridUnit=MIN,  majorGridStep=1,  labelUnit=SEC,  labelStep=15, format="%H:%M:%S"),
  dict(seconds=0.27,  minorGridUnit=SEC,  minorGridStep=30, majorGridUnit=MIN,  majorGridStep=2,  labelUnit=MIN,  labelStep=1,  format="%H:%M"),
  dict(seconds=0.5,   minorGridUnit=MIN,  minorGridStep=1,  majorGridUnit=MIN,  majorGridStep=2,  labelUnit=MIN,  labelStep=1,  format="%H:%M"),
  dict(seconds=1.0,   minorGridUnit=MIN,  minorGridStep=1,  majorGridUnit=MIN,  majorGridStep=4,  labelUnit=MIN,  labelStep=2,  format="%H:%M"),
  dict(seconds=2,     minorGridUnit=MIN,  minorGridStep=1,  majorGridUnit=MIN,  majorGridStep=10, labelUnit=MIN,  labelStep=5,  format="%H:%M"),
  dict(seconds=5,     minorGridUnit=MIN,  minorGridStep=2,  majorGridUnit=MIN,  majorGridStep=10, labelUnit=MIN,  labelStep=10, format="%H:%M"),
  dict(seconds=10,    minorGridUnit=MIN,  minorGridStep=5,  majorGridUnit=MIN,  majorGridStep=20, labelUnit=MIN,  labelStep=20, format="%H:%M"),
  dict(seconds=30,    minorGridUnit=MIN,  minorGridStep=10, majorGridUnit=HOUR, majorGridStep=1,  labelUnit=HOUR, labelStep=1,  format="%H:%M"),
  dict(seconds=60,    minorGridUnit=MIN,  minorGridStep=30, majorGridUnit=HOUR, majorGridStep=2,  labelUnit=HOUR, labelStep=2,  format="%H:%M", maxInterval=2*DAY),
  dict(seconds=180,   minorGridUnit=HOUR, minorGridStep=1,  majorGridUnit=HOUR, majorGridStep=6,  labelUnit=HOUR, labelStep=12,  format="%a %l%P"),
  dict(seconds=600,   minorGridUnit=HOUR, minorGridStep=6,  majorGridUnit=DAY,  majorGridStep=1,  labelUnit=DAY,  labelStep=1,  format="%a %l%P"),
  dict(seconds=1200,  minorGridUnit=HOUR, minorGridStep=6,  majorGridUnit=DAY,  majorGridStep=1,  labelUnit=DAY,  labelStep=1,  format="%m/%d"),
  dict(seconds=1800,  minorGridUnit=HOUR, minorGridStep=12, majorGridUnit=DAY,  majorGridStep=1,  labelUnit=DAY,  labelStep=2,  format="%a %d"),
  dict(seconds=2400,  minorGridUnit=HOUR, minorGridStep=12, majorGridUnit=DAY,  majorGridStep=1,  labelUnit=DAY,  labelStep=2,  format="%a"),
  dict(seconds=3600,  minorGridUnit=DAY,  minorGridStep=1,  majorGridUnit=WEEK, majorGridStep=1,  labelUnit=WEEK, labelStep=1,  format="Week %V"),
  dict(seconds=10800, minorGridUnit=WEEK, minorGridStep=1,  majorGridUnit=MONTH,majorGridStep=1,  labelUnit=WEEK, labelStep=2,  format="Week %V"),
  dict(seconds=21600, minorGridUnit=MONTH,minorGridStep=1,  majorGridUnit=MONTH,majorGridStep=1,  labelUnit=MONTH,labelStep=1,  format="%b"),
  dict(seconds=172800,minorGridUnit=MONTH,minorGridStep=1,  majorGridUnit=MONTH,majorGridStep=3,  labelUnit=MONTH,labelStep=3,  format="%b"),
  dict(seconds=864000,minorGridUnit=YEAR, minorGridStep=1,  majorGridUnit=YEAR, majorGridStep=1,  labelUnit=YEAR, labelStep=1,  format="%y"),
)


class Graph:
  customizable = ('width','height','margin','bgcolor','fgcolor', \
                 'fontName','fontSize','fontBold','fontItalic', \
                 'colorList','template')

  def __init__(self,**params):
    self.params = params
    self.data = params['data']
    self.width = int( params.get('width',200) )
    self.height = int( params.get('height',200) )
    self.margin = int( params.get('margin',10) )
    self.userTimeZoneOffset = tz_difference( params.get('tz','') )

    self.area = {
      'xmin' : self.margin,
      'xmax' : self.width - self.margin,
      'ymin' : self.margin,
      'ymax' : self.height - self.margin,
    }
    self.loadTemplate( params.get('template','default') )

    self.setupCairo( params.get('outputFormat','png').lower() )

    opts = self.ctx.get_font_options()
    opts.set_antialias( cairo.ANTIALIAS_NONE )
    self.ctx.set_font_options( opts )

    self.foregroundColor = params.get('fgcolor',self.defaultForeground)
    self.backgroundColor = params.get('bgcolor',self.defaultBackground)
    self.setColor( self.backgroundColor )
    self.drawRectangle( 0, 0, self.width, self.height )

    if 'colorList' in params:
      colorList = unquote_plus( params['colorList'] ).split(',')
    else:
      colorList = self.defaultColorList

    if 'randColors' in  params:
        import random
        rand_num = random.randint(0, len(colorList))
        self.colors =  itertools.cycle( colorList[rand_num:] + colorList[:rand_num] )
    else:
        self.colors = itertools.cycle( colorList )

    if 'randTargets' in params:
       import random
       random.shuffle(self.data)

    if self.data:
      self.drawGraph(**params)
    else:
      x = self.width / 2
      y = self.height / 2
      self.setColor('red')
      self.setFont(size=math.log(self.width * self.height) )
      self.drawText("No Data", x, y, align='center')

  def setupCairo(self,outputFormat='png'): #TODO Only PNG supported for now...
    #os.chdir( os.path.dirname(__file__) ) #To utilize local font-cache
    self.surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, self.width, self.height)
    self.ctx = cairo.Context(self.surface)

  def setColor(self, value, alpha=1.0):
    if type(value) is tuple and len(value) == 3:
      r,g,b = value
    elif value in colorAliases:
      r,g,b = colorAliases[value]
    elif type(value) in (str,unicode) and len(value) >= 6:
      s = value
      if s[0] == '#': s = s[1:]
      r,g,b = ( int(s[0:2],base=16), int(s[2:4],base=16), int(s[4:6],base=16) )
      if len(s) == 8:
        alpha = float( int(s[6:8],base=16) ) / 255.0
    else:
      raise ValueError, "Must specify an RGB 3-tuple, an html color string, or a known color alias!"
    r,g,b = [float(c) / 255.0 for c in (r,g,b)]
    self.ctx.set_source_rgba(r,g,b,alpha)

  def setFont(self, **params):
    p = self.defaultFontParams.copy()
    p.update(params)
    self.ctx.select_font_face(p['name'], p['italic'], p['bold'])
    self.ctx.set_font_size( float(p['size']) )

  def getExtents(self,text=None,fontOptions={}):
    if fontOptions:
      self.setFont(**fontOptions)
    F = self.ctx.font_extents()
    extents = { 'maxHeight' : F[2], 'maxAscent' : F[0], 'maxDescent' : F[1] }
    if text:
      T = self.ctx.text_extents(text)
      extents['width'] = T[4]
      extents['height'] = T[3]
    return extents

  def drawRectangle(self, x, y, w, h, fill=True, dash=False):
    if not fill:
      o = self.ctx.get_line_width() / 2.0 #offset for borders so they are drawn as lines would be
      x += o
      y += o
      w -= o
      h -= o
    self.ctx.rectangle(x,y,w,h)
    if fill:
      self.ctx.fill()
    else:
      if dash:
        self.ctx.set_dash(dash,1)
      else:
        self.ctx.set_dash([],0)
      self.ctx.stroke()

  def drawText(self,text,x,y,font={},color={},align='left',valign='top',border=False,rotate=0):
    if font: self.setFont(**font)
    if color: self.setColor(**color)
    extents = self.getExtents(text)
    angle = math.radians(rotate)
    origMatrix = self.ctx.get_matrix()

    horizontal = {
      'left' : 0,
      'center' : extents['width'] / 2,
      'right' : extents['width'],
    }[align.lower()]
    vertical = {
      'top' : extents['maxAscent'],
      'middle' : extents['maxHeight'] / 2 - extents['maxDescent'],
      'bottom' : -extents['maxDescent'],
      'baseline' : 0,
    }[valign.lower()]

    self.ctx.move_to(x,y)
    self.ctx.rel_move_to( math.sin(angle) * -vertical, math.cos(angle) * vertical)
    self.ctx.rotate(angle)
    self.ctx.rel_move_to( -horizontal, 0 )
    bx, by = self.ctx.get_current_point()
    by -= extents['maxAscent']
    self.ctx.text_path(text)
    self.ctx.fill()
    if border:
      self.drawRectangle(bx, by, extents['width'], extents['maxHeight'], fill=False)
    else:
      self.ctx.set_matrix(origMatrix)

  def drawTitle(self,text):
    y = self.area['ymin']
    x = self.width / 2
    lineHeight = self.getExtents()['maxHeight']
    for line in text.split('\n'):
      self.drawText(line, x, y, align='center')
      y += lineHeight
    self.area['ymin'] = y + self.margin

  def drawLegend(self,elements): #elements is [ (name,color), (name,color), ... ]
    longestName = sorted([e[0] for e in elements],key=len)[-1]
    extents = self.getExtents(longestName)
    padding = 4
    boxSize = extents['maxHeight'] - 1
    lineHeight = extents['maxHeight'] + 1
    labelWidth = extents['width'] + 2 * (boxSize + padding)
    columns = math.floor( self.width / labelWidth )
    if columns < 1: columns = 1
    numberOfLines = math.ceil( float(len(elements)) / columns )
    legendHeight = numberOfLines * (lineHeight + padding)
    self.area['ymax'] -= legendHeight #scoot the drawing area up to fit the legend
    self.ctx.set_line_width(1.0)
    x = self.area['xmin']
    y = self.area['ymax'] + (2 * padding)
    for i,(name,color) in enumerate(elements):
      self.setColor( color )
      self.drawRectangle(x,y,boxSize,boxSize)
      self.setColor( 'darkgrey' )
      self.drawRectangle(x,y,boxSize,boxSize,fill=False)
      self.setColor( self.foregroundColor )
      self.drawText(name, x + boxSize + padding, y, align='left')
      x += labelWidth
      if (i + 1) % columns == 0:
        x = self.area['xmin']
        y += lineHeight

  def loadTemplate(self,template):
    confFile = os.path.join(settings.WEB_DIR,'render','graphTemplates.conf')
    conf = SafeConfigParser()
    conf.read(confFile)
    defaults = dict( conf.items('default') )
    if template in conf.sections():
      opts = dict( conf.items(template) )
    else:
      opts = defaults
    self.defaultBackground = opts.get('background', defaults['background'])
    self.defaultForeground = opts.get('foreground', defaults['foreground'])
    self.defaultMajorGridLineColor = opts.get('majorline', defaults['majorline'])
    self.defaultMinorGridLineColor = opts.get('minorline', defaults['minorline'])
    self.defaultColorList = [c.strip() for c in opts.get('linecolors', defaults['linecolors']).split(',')]
    fontName = opts.get('fontname', defaults['fontname'])
    fontSize = float( opts.get('fontsize', defaults['fontsize']) )
    fontBold = opts.get('fontbold', defaults['fontbold']).lower() == 'true'
    fontItalic = opts.get('fontitalic', defaults['fontitalic']).lower() == 'true'
    self.defaultFontParams = {
      'name' : self.params.get('fontName',fontName),
      'size' : int( self.params.get('fontSize',fontSize) ),
      'bold' : self.params.get('fontBold',fontBold),
      'italic' : self.params.get('fontItalic',fontItalic),
    }

  def output(self, fileObj):
    self.surface.write_to_png(fileObj)


class LineGraph(Graph):
  customizable = Graph.customizable + \
                 ('title','vtitle','lineMode','lineWidth','hideLegend', \
                  'hideAxes','minXStep','hideGrid','majorGridLineColor', \
                  'minorGridLineColor','thickness','min','max', \
                  'graphOnly','yMin','yMax','yStep','areaMode','drawNullAsZero','tz',
		  'randColors', 'randTargets')
  validLineModes = ('staircase','slope')
  validAreaModes = ('none','first','all','stacked')

  def drawGraph(self,**params):
    #API compatibilty hacks first
    if params.get('graphOnly',False):
      params['hideLegend'] = True
      params['hideGrid'] = True
      params['hideAxes'] = True
      params['title'] = ''
      params['vtitle'] = ''
      params['margin'] = 0
      params['tz'] = ''
      self.margin = 0
      self.area['xmin'] = 0
      self.area['xmax'] = self.width
      self.area['ymin'] = 0
      self.area['ymax'] = self.height
    if 'yMin' not in params and 'min' in params:
      params['yMin'] = params['min']
    if 'yMax' not in params and 'max' in params:
      params['yMax'] = params['max']
    if 'lineWidth' not in params and 'thickness' in params:
      params['lineWidth'] = params['thickness']
    self.params = params

    #Now to setup our LineGraph specific options
    self.lineWidth = float( params.get('lineWidth', 1.2) )
    self.lineMode = params.get('lineMode','slope').lower()
    assert self.lineMode in self.validLineModes, "Invalid line mode!"
    self.areaMode = params.get('areaMode','none').lower()
    assert self.areaMode in self.validAreaModes, "Invalid area mode!"

    for series in self.data:
      series.color = self.colors.next()

    titleSize = self.defaultFontParams['size'] + math.floor( math.log(self.defaultFontParams['size']) )
    self.setFont( size=titleSize )
    self.setColor( self.foregroundColor )
    if params.get('title'):
      self.drawTitle( str(params['title']) )
    if params.get('vtitle'):
      self.drawVTitle( str(params['vtitle']) )
    self.setFont()

    if not params.get('hideLegend', 0):
      elements = [ (series.name,series.color) for series in self.data ]
      self.drawLegend(elements)

    #Setup axes, labels, and grid
    #First we adjust the drawing area size to fit X-axis labels
    if not self.params.get('hideAxes',False):
      self.area['ymax'] -= self.getExtents()['maxAscent'] * 2

    #Now we consolidate our data points to fit in the currently estimated drawing area
    self.consolidateDataPoints()

    #Now its time to fully configure the Y-axis and determine the space required for Y-axis labels
    #Since we'll probably have to squeeze the drawing area to fit the Y labels, we may need to
    #reconsolidate our data points, which in turn means re-scaling the Y axis, this process will
    #repeat until we have accurate Y labels and enough space to fit our data points
    currentXMin = self.area['xmin']
    self.setupYAxis()
    while currentXMin != self.area['xmin']: #see if the Y-labels require more space
      self.consolidateDataPoints() #this can cause the Y values to change
      currentXMin = self.area['xmin'] #so let's keep track of the previous Y-label space requirements
      self.setupYAxis() #and recalculate their new requirements

    #Now that our Y-axis is finalized, let's determine our X labels (this won't affect the drawing area)
    self.setupXAxis()

    if not self.params.get('hideAxes',False):
      self.drawLabels()
      if not self.params.get('hideGrid',False): #hideAxes implies hideGrid
        self.drawGridLines()

    #Finally, draw the graph lines
    self.drawLines()

  def drawVTitle(self,text):
    lineHeight = self.getExtents()['maxHeight']
    x = self.area['xmin'] + lineHeight
    y = self.height / 2
    for line in text.split('\n'):
      self.drawText(line, x, y, align='center', valign='baseline', rotate=270)
      x += lineHeight
    self.area['xmin'] = x + self.margin + lineHeight

  def drawLines(self, width=None, dash=None, linecap='butt', linejoin='miter'):
    if not width: width = self.lineWidth
    self.ctx.set_line_width(width)
    originalWidth = width
    width = float(int(width) % 2) / 2
    if dash:
      self.ctx.set_dash(dash,1)
    else:
      self.ctx.set_dash([],0)
    self.ctx.set_line_cap({
      'butt' : cairo.LINE_CAP_BUTT,
      'round' : cairo.LINE_CAP_ROUND,
      'square' : cairo.LINE_CAP_SQUARE,
    }[linecap])
    self.ctx.set_line_join({
      'miter' : cairo.LINE_JOIN_MITER,
      'round' : cairo.LINE_JOIN_ROUND,
      'bevel' : cairo.LINE_JOIN_BEVEL,
    }[linejoin])

    # stack the values
    if self.areaMode == 'stacked':
      total = []
      for series in self.data:
        for i in range(len(series)):
          if len(total) <= i: total.append(0)

          if series[i] is not None:
            original = series[i]
            series[i] += total[i]
            total[i] += original

      self.data = reverse_sort(self.data)

    # setup the clip region
    self.ctx.set_line_width(1.0)
    self.ctx.rectangle(self.area['xmin'], self.area['ymin'], self.area['xmax'] - self.area['xmin'], self.area['ymax'] - self.area['ymin'])
    self.ctx.clip()
    self.ctx.set_line_width(originalWidth)

    for series in self.data:

      if series.options.has_key('lineWidth'): # adjusts the lineWidth of this line if option is set on the series
        self.ctx.set_line_width(series.options['lineWidth'])

      if series.options.has_key('dashed'): # turn on dashing if dashed option set
        self.ctx.set_dash([ series.options['dashed'] ],1)
      else:
        self.ctx.set_dash([], 0)

      x = float(self.area['xmin']) + (self.lineWidth / 2.0)
      y = float(self.area['ymin'])
      self.setColor( series.color )

      fromNone = True

      for value in series:
        if value is None and self.params.get('drawNullAsZero'):
          value = 0.0

        if value is None:

          if not fromNone and self.areaMode != 'none': #Close off and fill area before unknown interval
            self.ctx.line_to(x, self.area['ymax'])
            self.ctx.close_path()
            self.ctx.fill()
          x += series.xStep
          fromNone = True

        else:
          y = self.area['ymax'] - ((float(value) - self.yBottom) * self.yScaleFactor)

          if series.options.has_key('drawAsInfinite') and value > 0:
            self.ctx.move_to(x, self.area['ymax'])
            self.ctx.line_to(x, self.area['ymin'])
            self.ctx.stroke()
            x += series.xStep
            continue

          if self.lineMode == 'staircase':
            if fromNone:

              if self.areaMode != 'none':
                self.ctx.move_to(x,self.area['ymax'])
                self.ctx.line_to(x,y)
              else:
                self.ctx.move_to(x,y)

            else:
              self.ctx.line_to(x,y)

            x += series.xStep
            self.ctx.line_to(x,y)

          elif self.lineMode == 'slope':
            if fromNone:

              if self.areaMode != 'none':
                self.ctx.move_to(x,self.area['ymax'])
                self.ctx.line_to(x,y)
              else:
                self.ctx.move_to(x,y)

            x += series.xStep
            self.ctx.line_to(x,y)

          fromNone = False

      if self.areaMode != 'none':
        self.ctx.line_to(x, self.area['ymax'])
        self.ctx.close_path()
        self.ctx.fill()

        if self.areaMode == 'first':
          self.areaMode = 'none' #This ensures only the first line is drawn as area

      else:
        self.ctx.stroke()

      self.ctx.set_line_width(originalWidth) # return to the original line width
      if series.options.has_key('dash'): # if we changed the dash setting before, change it back now
        if dash:
          self.ctx.set_dash(dash,1)
        else:
          self.ctx.set_dash([],0)

  def consolidateDataPoints(self):
    numberOfPixels = self.graphWidth = self.area['xmax'] - self.area['xmin'] - (self.lineWidth + 1)
    for series in self.data:
      numberOfDataPoints = len(series)
      minXStep = float( self.params.get('minXStep',1.0) )
      bestXStep = numberOfPixels / numberOfDataPoints
      if bestXStep < minXStep:
        drawableDataPoints = int( numberOfPixels / minXStep )
        pointsPerPixel = math.ceil( float(numberOfDataPoints) / float(drawableDataPoints) )
        series.consolidate(pointsPerPixel)
        series.xStep = (numberOfPixels * pointsPerPixel) / numberOfDataPoints
      else:
        series.xStep = bestXStep

  def setupYAxis(self):
    seriesWithMissingValues = [ series for series in self.data if None in series ]

    if self.params.get('drawNullAsZero') and seriesWithMissingValues:
      yMinValue = 0.0
    else:
      yMinValue = safeMin( [safeMin(series) for series in self.data] )

    if self.areaMode == 'stacked':
      yMaxValue = safeSum( [safeMax(series) for series in self.data] )
    else:
      yMaxValue = safeMax( [safeMax(series) for series in self.data] )

    if yMinValue is None:
      yMinValue = 0.0

    if yMaxValue is None:
      yMaxValue = 1.0

    if 'yMax' in self.params:
      yMaxValue = self.params['yMax']

    if 'yMin' in self.params:
      yMinvalue = self.params['yMin']

    yVariance = yMaxValue - yMinValue

    if math.floor(yVariance) == 0:
      yVariance = 1
      yMaxValue = yMinValue + 1

    order = math.log10(yVariance)
    orderFactor = 10 ** math.floor(order)
    v = yVariance / orderFactor #we work with a scaled down yVariance for simplicity

    divisors = (4,5,6) #different ways to divide-up the y-axis with labels
    prettyValues = (0.1,0.2,0.25,0.5,1.0,1.2,1.25,1.5,2.0,2.25,2.5)
    divisorInfo = []

    for d in divisors:
      q = v / d #our scaled down quotient, must be in the open interval (0,10)
      p = closest(q, prettyValues) #the prettyValue our quotient is closest to
      divisorInfo.append( ( p,abs(q-p)) ) #make a list so we can find the prettiest of the pretty

    divisorInfo.sort(key=lambda i: i[1]) #sort our pretty values by "closeness to a factor"
    prettyValue = divisorInfo[0][0] #our winner! Y-axis will have labels placed at multiples of our prettyValue
    self.yStep = prettyValue * orderFactor #scale it back up to the order of yVariance

    if 'yStep' in self.params:
      self.yStep = self.params['yStep']

    self.yBottom = self.yStep * math.floor( yMinValue / self.yStep ) #start labels at the greatest multiple of yStep <= yMinValue
    self.yTop = self.yStep * math.ceil( yMaxValue / self.yStep ) #Extend the top of our graph to the lowest yStep multiple >= yMaxValue

    if 'yMax' in self.params:
      self.yTop = self.params['yMax']
    if 'yMin' in self.params:
      self.yBottom = self.params['yMin']

    self.ySpan = self.yTop - self.yBottom

    if self.ySpan == 0:
      self.yTop += 1
      self.ySpan += 1

    self.graphHeight = self.area['ymax'] - self.area['ymin']
    self.yScaleFactor = float(self.graphHeight) / float(self.ySpan)

    if not self.params.get('hideAxes',False):
      #Create and measure the Y-labels
      def makeLabel(yValue): #TODO beautify this!
        if self.ySpan > 10:
          return "%d " % int(yValue)
        elif self.ySpan > 3:
          return "%.1f " % float(yValue)
        else:
          return "%.2f " % float(yValue)
      self.yLabelValues = list( frange(self.yBottom,self.yTop,self.yStep) )
      self.yLabels = map(makeLabel,self.yLabelValues)
      self.yLabelWidth = max([self.getExtents(label)['width'] for label in self.yLabels])
      xMin = self.margin + (self.yLabelWidth * 1.02)
      if self.area['xmin'] < xMin:
        self.area['xmin'] = xMin #scoot the graph over to the right just enough to fit the y-labels
    else:
      self.yLabelValues = []
      self.yLabels = []
      self.yLabelWidth = 0.0

  def setupXAxis(self):
    self.startTime = min([series.start for series in self.data])
    self.endTime = max([series.end for series in self.data])
    timeRange = self.endTime - self.startTime

    secondsPerPixel = float(timeRange) / float(self.graphWidth)
    self.xScaleFactor = float(self.graphWidth) / float(timeRange) #pixels per second

    potential = [c for c in xAxisConfigs if c['seconds'] <= secondsPerPixel and c.get('maxInterval',timeRange+1) > timeRange]
    if potential:
      self.xConf = potential[-1]
    else:
      self.xConf = xAxisConfigs[-1]

    self.xLabelStep = self.xConf['labelUnit'] * self.xConf['labelStep']
    self.xMinorGridStep = self.xConf['minorGridUnit'] * self.xConf['minorGridStep']
    self.xMajorGridStep = self.xConf['majorGridUnit'] * self.xConf['majorGridStep']
    if self.xConf['labelUnit'] >= DAY: #JIRA SOS-80
      if daylight:
        self.utcAdjustment = altzone
      else:
        self.utcAdjustment = timezone
    else:
      self.utcAdjustment = 0

  def drawLabels(self):
    #Draw the Y-labels
    for value,label in zip(self.yLabelValues,self.yLabels):
      x = self.area['xmin'] - (self.yLabelWidth * 0.02)
      y = self.area['ymax'] - ((value - self.yBottom) * self.yScaleFactor)
      self.drawText(label,x,y,align='right',valign='middle')
    t = self.xLabelStep * math.ceil( float(self.startTime) / self.xLabelStep )

    #Draw the X-labels
    while t < self.endTime:
      label = strftime(self.xConf['format'], localtime(t + self.utcAdjustment + self.userTimeZoneOffset ))
      x = self.area['xmin'] + ((t - self.startTime) * self.xScaleFactor)
      y = self.area['ymax'] + self.getExtents()['maxAscent']
      self.drawText(label,x,y,align='center',valign='top')
      t += self.xLabelStep

  def drawGridLines(self):
    #Horizontal grid lines
    leftSide = self.area['xmin']
    rightSide = self.area['xmax']
    for value in self.yLabelValues:
      self.ctx.set_line_width(0.4)
      self.setColor( self.params.get('majorGridLineColor',self.defaultMajorGridLineColor) )
      y = self.area['ymax'] - ((value - self.yBottom) * self.yScaleFactor)
      self.ctx.move_to(leftSide, y)
      self.ctx.line_to(rightSide, y)
      self.ctx.stroke()
      self.ctx.set_line_width(0.3)
      self.setColor( self.params.get('minorGridLineColor',self.defaultMinorGridLineColor) )
      value += (self.yStep / 2.0)
      if value >= self.yTop: continue
      y = self.area['ymax'] - ((value - self.yBottom) * self.yScaleFactor)
      self.ctx.move_to(leftSide, y)
      self.ctx.line_to(rightSide, y)
      self.ctx.stroke()
    #Vertical grid lines
    top = self.area['ymin']
    bottom = self.area['ymax']
    self.ctx.set_line_width(0.25) #First we do minor lines (major's should paint over them)
    self.setColor( self.params.get('minorGridLineColor',self.defaultMinorGridLineColor) )
    t = self.xMinorGridStep * math.ceil( float(self.startTime) / self.xMinorGridStep )
    while t < self.endTime:
      x = self.area['xmin'] + ((t - self.startTime) * self.xScaleFactor)
      self.ctx.move_to(x, bottom)
      self.ctx.line_to(x, top)
      self.ctx.stroke()
      t += self.xMinorGridStep
    self.ctx.set_line_width(0.33) #Now for the major grid lines
    self.setColor( self.params.get('majorGridLineColor',self.defaultMajorGridLineColor) )
    t = self.xMajorGridStep * math.ceil( float(self.startTime) / self.xMajorGridStep )
    while t < self.endTime:
      x = self.area['xmin'] + ((t - self.startTime) * self.xScaleFactor)
      self.ctx.move_to(x, bottom)
      self.ctx.line_to(x, top)
      self.ctx.stroke()
      t += self.xMajorGridStep
    #Draw side borders for our graph area
    self.ctx.set_line_width(0.5)
    self.ctx.move_to(self.area['xmax'], bottom)
    self.ctx.line_to(self.area['xmax'], top)
    self.ctx.move_to(self.area['xmin'], bottom)
    self.ctx.line_to(self.area['xmin'], top)
    self.ctx.stroke()


class PieGraph(Graph):
  customizable = Graph.customizable + \
                 ('title','valueLabels','valueLabelsMin','hideLegend')
  validValueLabels = ('none','number','percent')

  def drawGraph(self,**params):
    self.total = sum( [t[1] for t in self.data] )

    self.slices = []
    for name,value in self.data:
      self.slices.append({
        'name' : name,
        'value' : value,
        'percent' : value / self.total,
        'color' : self.colors.next(),
      })

    titleSize = self.defaultFontParams['size'] + math.floor( math.log(self.defaultFontParams['size']) )
    self.setFont( size=titleSize )
    self.setColor( self.foregroundColor )
    if params.get('title'):
      self.drawTitle( params['title'] )
    self.setFont()

    if not params.get('hideLegend',False):
      elements = [ (slice['name'],slice['color']) for slice in self.slices ]
      self.drawLegend(elements)

    self.drawSlices()

    self.valueLabelsMin = float( params.get('valueLabelsMin',5) )
    self.valueLabels = params.get('valueLabels','percent')
    assert self.valueLabels in self.validValueLabels, \
    "valueLabels=%s must be one of %s" % (self.valueLabels,self.validValueLabels)
    if self.valueLabels != 'none':
      self.drawLabels()

  def drawSlices(self):
    theta = 3.0 * math.pi / 2.0
    halfX = (self.area['xmax'] - self.area['xmin']) / 2.0
    halfY = (self.area['ymax'] - self.area['ymin']) / 2.0
    self.x0 = x0 = self.area['xmin'] + halfX
    self.y0 = y0 = self.area['ymin'] + halfY
    self.radius = radius = min(halfX,halfY) * 0.95
    for slice in self.slices:
      self.setColor( slice['color'] )
      self.ctx.move_to(x0,y0)
      phi = theta + (2 * math.pi) * slice['percent']
      self.ctx.arc( x0, y0, radius, theta, phi )
      self.ctx.line_to(x0,y0)
      self.ctx.fill()
      slice['midAngle'] = (theta + phi) / 2.0
      slice['midAngle'] %= 2.0 * math.pi
      theta = phi

  def drawLabels(self):
    self.setFont()
    self.setColor( self.foregroundColor )
    for slice in self.slices:
      if self.valueLabels == 'percent':
        if (slice['percent'] * 100.0) < self.valueLabelsMin: continue
        label = "%%%.2f" % (slice['percent'] * 100.0)
      elif self.valueLabels == 'number':
        if slice['value'] < self.valueLabelsMin: continue
        if slice['value'] < 10 and slice['value'] != int(slice['value']):
          label = "%.2f" % slice['value']
        else:
          label = str(int(slice['value']))
      extents = self.getExtents(label)
      theta = slice['midAngle']
      x = self.x0 + (self.radius / 2.0 * math.cos(theta))
      y = self.y0 + (self.radius / 2.0 * math.sin(theta))
      if theta > (math.pi / 2.0) and theta <= (3.0 * math.pi / 2.0):
        theta -= math.pi
      self.drawText( label, x, y, align='center', valign='middle', rotate=math.degrees(theta) )


GraphTypes = {
  'line' : LineGraph,
  'pie' : PieGraph,
}

#Convience functions ... put these in milton?
def closest(number,neighbors):
  distance = None
  closestNeighbor = None
  for neighbor in neighbors:
    d = abs(neighbor - number)
    if distance is None or d < distance:
      distance = d
      closestNeighbor = neighbor
  return closestNeighbor

def frange(start,end,step):
  f = start
  while f <= end:
    yield f
    f += step

def toSeconds(t):
  return (t.days * 86400) + t.seconds

def safeMin(args):
  args = [arg for arg in args if arg is not None]
  if args:
    return min(args)

def safeMax(args):
  args = [arg for arg in args if arg is not None]
  if args:
    return max(args)

def safeSum(values):
  return sum([v for v in values if v is not None])

def any(args):
  for arg in args:
    if arg:
      return True
  return False

def reverse_sort(args):
  aux_list = [arg for arg in args]
  aux_list.reverse()
  return aux_list
 
def tz_difference(tz):
  os.environ['TZ'] = tz
  tzset()
  captured_time = localtime()
  tz_delta = int(timegm(captured_time) - mktime(captured_time))

  try:
    os.environ['TZ'] = local_settings.TIME_ZONE
  except:
    os.environ['TZ'] = settings.TIME_ZONE
  return tz_delta
