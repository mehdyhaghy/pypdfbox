class Bitmap:
    """A bi-level image that is organized like a bitmap.

    The image data is stored in a byte array. Each pixel is stored as one bit,
    so that each byte contains 8 pixels. A pixel has by default the value ``0``
    for white and ``1`` for black. Bits are packed MSB-first within each byte:
    the leftmost pixel of a byte occupies the most significant bit.
    """

    def __init__(self, width: int, height: int) -> None:
        """Create a blank bitmap of the given dimensions.

        Row stride means the amount of bytes per line. It is computed
        automatically and the pad bits are filled with ``0``.

        :param width: The real width of the bitmap in pixels.
        :param height: The real height of the bitmap in pixels.
        """
        self.height = height
        self.width = width
        self.row_stride = (width + 7) >> 3

        self.bitmap_bytes = bytearray(self.height * self.row_stride)

    def get_pixel(self, x: int, y: int) -> int:
        """Return the value of the pixel at the given coordinates.

        By default, the value is ``0`` for a white pixel and ``1`` for a black
        pixel. The value is placed in the rightmost bit in the byte. There is no
        check whether the pixel coordinate is within the bitmap.
        """
        byte_index = self.get_byte_index(x, y)
        bit_offset = self.get_bit_offset(x)

        to_shift = 7 - bit_offset
        return (self.get_byte(byte_index) >> to_shift) & 0x01

    def set_pixel(self, x: int, y: int, pixel_value: int) -> None:
        """Set the value of the pixel at the given coordinates.

        By default, the value is ``0`` for a white pixel and ``1`` for a black
        pixel. The value is taken from the rightmost bit. There is no check
        whether the pixel coordinate is within the bitmap.
        """
        byte_index = self.get_byte_index(x, y)
        bit_offset = self.get_bit_offset(x)

        shift = 7 - bit_offset

        src = self.bitmap_bytes[byte_index] & 0xFF
        if (pixel_value & 1) == 1:
            self.bitmap_bytes[byte_index] = (src | (1 << shift)) & 0xFF
        else:
            self.bitmap_bytes[byte_index] = (src & ~(1 << shift)) & 0xFF

    def get_byte_index(self, x: int, y: int) -> int:
        """Return the index of the byte that contains the pixel at (x, y)."""
        return y * self.row_stride + (x >> 3)

    def get_byte_array(self) -> bytearray:
        """Return the underlying byte array of this bitmap.

        .. deprecated:: don't expose the underlying byte array; will be removed
           in a future release.
        """
        return self.bitmap_bytes

    def get_byte(self, index: int) -> int:
        """Return a byte from the bitmap byte array.

        :raises IndexError: if the index is out of bound.
        """
        return self.bitmap_bytes[index]

    def set_byte(self, index: int, value: int) -> None:
        """Set the given value at the given array index position.

        :raises IndexError: if the index is out of bound.
        """
        self.bitmap_bytes[index] = value & 0xFF

    def get_byte_as_integer(self, index: int) -> int:
        """Return the byte at the specified index as an unsigned integer.

        :raises IndexError: if the index is out of bound.
        """
        return self.bitmap_bytes[index] & 0xFF

    def get_bit_offset(self, x: int) -> int:
        """Return the bit offset of the given x coordinate within its byte.

        This is the same as ``x % 8``.
        """
        return x & 0x07

    def get_height(self) -> int:
        """Return the height of this bitmap."""
        return self.height

    def get_width(self) -> int:
        """Return the width of this bitmap."""
        return self.width

    def get_row_stride(self) -> int:
        """Return the row stride (amount of bytes per line) of this bitmap."""
        return self.row_stride

    def get_bounds(self) -> tuple[int, int, int, int]:
        # Upstream returns a java.awt.Rectangle(0, 0, width, height). The only
        # callers live in image/Bitmaps.java (a later wave) which use
        # Rectangle.equals()/intersection(); when that wave lands it should
        # replace this with the ported integer Rectangle type. For now a plain
        # (x, y, width, height) tuple captures the same data.
        return (0, 0, self.width, self.height)

    def get_memory_size(self) -> int:
        """Return the length of the underlying byte array.

        .. deprecated:: renamed; will be removed in a future release. Use
           :meth:`get_length` instead.
        """
        return self.get_length()

    def get_length(self) -> int:
        """Return the length of the underlying byte array."""
        return len(self.bitmap_bytes)

    def fill_bitmap(self, fill_byte: int) -> None:
        """Fill the underlying bitmap with the given byte value."""
        fill_byte &= 0xFF
        for i in range(len(self.bitmap_bytes)):
            self.bitmap_bytes[i] = fill_byte

    def __eq__(self, obj: object) -> bool:
        # most likely used for tests
        if not isinstance(obj, Bitmap):
            return False
        other = obj
        if self.bitmap_bytes == other.bitmap_bytes:
            return True
        # the last byte can have differences e.g. because XNOR puts 1 in unused
        # parts; maybe pixel difference
        if self.width != other.width or self.height != other.height:
            return False
        if (self.width % 8) == 0:
            return False  # no extra bits, thus unequal for sure
        p = (self.row_stride - 1) * 8  # index of first pixel in last byte
        for y in range(self.height):
            # compare stride except last byte
            idx = self.get_byte_index(0, y)
            for i in range(idx, idx + self.row_stride - 1):
                if self.bitmap_bytes[i] != other.bitmap_bytes[i]:
                    return False
            # compare the last bits
            for x in range(p, self.width):
                if self.get_pixel(x, y) != other.get_pixel(x, y):
                    return False
        return True

    def __hash__(self) -> int:
        hash_value = 7
        hash_value = 59 * hash_value + self.height
        hash_value = 59 * hash_value + self.width
        hash_value = 59 * hash_value + self.row_stride
        hash_value = 59 * hash_value + hash(bytes(self.bitmap_bytes))
        return hash_value

    @staticmethod
    def arraycopy(
        src: Bitmap, src_pos: int, dest: Bitmap, dest_pos: int, length: int
    ) -> None:
        """Copy parts of the underlying array of one Bitmap to another.

        :param src: the source Bitmap.
        :param src_pos: start position within the source Bitmap.
        :param dest: the destination Bitmap.
        :param dest_pos: start position within the destination Bitmap.
        :param length: the number of bytes to be copied.
        """
        dest.bitmap_bytes[dest_pos:dest_pos + length] = src.bitmap_bytes[
            src_pos:src_pos + length
        ]
