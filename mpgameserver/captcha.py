
import math
import random
import secrets

import os
import pygame
from PIL import Image, ImageFont, ImageDraw, ImageOps
from io import BytesIO

from cryptography.hazmat.primitives.constant_time import bytes_eq

class Captcha():
    """

    Note: the default settings for both create() and getBytes() are tuned
    to produce an image which will fit inside of a single UDP packet, and
    allow for some overhead

    :attr code: the string contained in the image
    :attr image: the image challenge

    """
    def __init__(self, code, image):
        super(Captcha, self).__init__()
        self.code = code
        self.image = image

    def getBytes(self, quality=25):
        """
        :param path: a file path to save the captcha to
        :param quality: 0 to 100, default 25. use 75 for 'best quality'
        see the PIL documentation for more information
        """

        data = BytesIO()
        self.image.save(data, format='JPEG', quality=quality)
        return data.getvalue()

    def validate(self, text):
        """ compare a given string to the code

        Performs a constant time comparison that is case insensitive.

        returns true when the given text matches the code

        """

        expected = self.code.lower().encode("utf-8")
        actual = text.lower().encode("utf-8")
        return bytes_eq(expected, actual)

    @staticmethod
    def create(font_file=None, code_length=5, bgc=(255,255,255), size=(100,25), rotate=60):
        """

        :param bgc: the background color of the image
        :param size: a 2-tuple (width, height) in pixels
        :param rotate: maximum degrees to rotate a single character.
        a character will be rotated by a random value +/- rotate/2
        """

        if font_file is None:
            pygame.font.init()
            path = os.path.split(pygame.font.__file__)[0]
            font_file = os.path.join(path, pygame.font.get_default_font())

        # everything except 1,L,l,I,i,0,O,o
        # note chars will be case insensitive
        chars = "ABCDEFGHJKMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz"
        nums = "23456789"

        code = ""
        for i in range(code_length):
            code += random.choice(random.choice([chars, nums]))

        image = Image.new('RGB', size, bgc)
        w_char = size[0]//code_length
        h_char = size[1]

        font_size = 20 # h_char * 3//4
        dx = w_char//4
        dy = 0 # size[1]//4

        font = ImageFont.truetype(font_file, font_size)

        offset = 0
        for char in code:
            img_char = Image.new('RGB', (w_char, h_char), bgc)
            draw = ImageDraw.Draw(img_char)
            dyo = dy + random.randint(0, size[1]//4)
            draw.text( (dx, dyo), char, fill='black', font=font)
            angle = random.randrange(rotate) - rotate//2
            img_char_rotated = img_char.rotate(angle,  fillcolor=bgc)
            image.paste(img_char_rotated, (offset, 0))
            offset += w_char

        #draw = ImageDraw.Draw(image)
        #draw.line([(0,size[1]//2),(size[0], size[1]//2)], fill=(200,0,0), width=2)


        captcha = Captcha(code, image)
        captcha.code = code
        captcha.image = image

        return captcha

def main():  # pragma: no cover

    path = "out.jpg"
    captcha = Captcha.create(size=(100,25))

    print(captcha.code)
    with open(path, "wb") as jpg:
        jpg.write(captcha.getBytes())
        print("wrote %d bytes to %s" % (jpg.tell(), path))

if __name__ == '__main__':  # pragma: no cover
    main()