
import os
import pygame
import time

class TileSheetBuilder(object):
    def __init__(self):
        super(TileSheetBuilder, self).__init__()

        self.colorkey_c = None
        self.colorkey_x = None
        self.colorkey_y = None
        self.offset_x = 0
        self.offset_y = 0
        self.spacing_x = 0
        self.spacing_y = 0
        self.rows = -1
        self.cols = -1
        self.width = 0
        self.height = 0

        self._images = []

    def colorkey(self, c_x, y=None):
        """
        colorkey(color) set the alpha color to alpha
        colorkey(x, y)  set the alpha color to the color of the pixel at (x,y)
        """

        if y is None:
            self.colorkey_c = c_x
        else:
            self.colorkey_x = c_x
            self.colorkey_y = y
            self.colorkey_c = None

        return self

    def offset(self, x, y):
        """
        starting position of the tile sheet in the image
        """
        self.offset_x = x;
        self.offset_y = y;
        return self

    def spacing(self, x, y):
        """
        space between each tile
        """
        self.spacing_x = x;
        self.spacing_y = y;
        return self

    def dimensions(self, w, h):
        """
        size of each tile
        """
        self.width = w;
        self.height = h;
        return self

    def layout(self, rows, cols):
        """
        number of rows and columns
        set to -1 to mean as many as possible
        """
        self.rows = rows;
        self.cols = cols;
        return self

    def build(self, path):
        """
        it is faster to load a png with an alpha layer already set
        than to load an image and use a color key
        """

        #t0 = time.time()
        if not os.path.exists(path):
            raise FileNotFoundError(path)
        if isinstance(path, str):
            sheet = pygame.image.load(path)
            if path.lower().endswith(".png"):
                sheet = sheet.convert_alpha()
        else:
            sheet = path

        if self.height == 0:
            raise ValueError("set height")

        if self.width == 0:
            raise ValueError("set width")

        cols = self.cols
        rows = self.rows

        if cols < 0:
            cols = (sheet.get_width() - self.offset_x) // (self.width + self.spacing_x)

        if rows < 0:
            rows = (sheet.get_height() - self.offset_y) // (self.height + self.spacing_y)

        images = []

        colorkey = None

        if self.colorkey_c is None:
            if self.colorkey_x is not None:
                colorkey = sheet.get_at((self.colorkey_x,self.colorkey_y))
        else:
            colorkey = self.colorkey_c

        if colorkey is not None:
            sheet.set_colorkey(self.colorkey_c, pygame.RLEACCEL)

        for i in range(rows):
            for j in range(cols):

                x = self.offset_x + (self.width + self.spacing_x) * j
                y = self.offset_y + (self.height + self.spacing_y) * i

                rect = pygame.Rect(x,y,self.width, self.height)
                image = pygame.Surface(rect.size).convert_alpha()
                image.fill((0,0,0,0))
                image.blit(sheet, (0, 0), rect)

                images.append(image)

        self.nrows = rows
        self.ncols = cols

        #print("elapsed: %.2f" % (time.time() - t0))

        return images
