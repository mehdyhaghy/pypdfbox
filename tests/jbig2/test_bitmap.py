from pypdfbox.jbig2.bitmap import Bitmap


def test_dimensions_and_row_stride():
    bm = Bitmap(10, 5)
    assert bm.get_width() == 10
    assert bm.get_height() == 5
    # 10 pixels -> ceil(10/8) = 2 bytes per row
    assert bm.get_row_stride() == 2
    assert bm.get_length() == 5 * 2
    assert bm.get_memory_size() == bm.get_length()


def test_row_stride_exact_multiple_of_eight():
    bm = Bitmap(16, 3)
    assert bm.get_row_stride() == 2
    bm2 = Bitmap(8, 1)
    assert bm2.get_row_stride() == 1
    bm3 = Bitmap(1, 1)
    assert bm3.get_row_stride() == 1


def test_blank_bitmap_is_all_zero():
    bm = Bitmap(20, 4)
    for y in range(4):
        for x in range(20):
            assert bm.get_pixel(x, y) == 0


def test_set_and_get_pixel():
    bm = Bitmap(8, 1)
    bm.set_pixel(3, 0, 1)
    assert bm.get_pixel(3, 0) == 1
    # neighbours untouched
    assert bm.get_pixel(2, 0) == 0
    assert bm.get_pixel(4, 0) == 0
    # clearing
    bm.set_pixel(3, 0, 0)
    assert bm.get_pixel(3, 0) == 0


def test_msb_first_packing_layout():
    # leftmost pixel (x=0) must occupy the most significant bit of byte 0
    bm = Bitmap(8, 1)
    bm.set_pixel(0, 0, 1)
    assert bm.get_byte(0) == 0x80  # 1000_0000
    assert bm.get_byte_as_integer(0) == 0x80

    bm = Bitmap(8, 1)
    bm.set_pixel(7, 0, 1)
    assert bm.get_byte(0) == 0x01  # 0000_0001

    bm = Bitmap(8, 1)
    bm.set_pixel(1, 0, 1)
    bm.set_pixel(2, 0, 1)
    assert bm.get_byte(0) == 0x60  # 0110_0000


def test_pixel_value_only_uses_low_bit():
    bm = Bitmap(8, 1)
    # any odd value sets the pixel, any even value clears it
    bm.set_pixel(0, 0, 3)
    assert bm.get_pixel(0, 0) == 1
    bm.set_pixel(0, 0, 2)
    assert bm.get_pixel(0, 0) == 0


def test_set_pixel_across_byte_boundary():
    bm = Bitmap(20, 2)
    # x=8 lives in the 2nd byte of the row (byte index 1) at its MSB
    bm.set_pixel(8, 0, 1)
    assert bm.get_pixel(8, 0) == 1
    assert bm.get_byte_index(8, 0) == 1
    assert bm.get_byte(1) == 0x80
    # x=19 lives in the 3rd byte (byte index 2)
    bm.set_pixel(19, 1, 1)
    assert bm.get_pixel(19, 1) == 1
    # row 1 starts at byte index 1 (rowStride) * 1 = 3; x=19 -> +2 = 5
    assert bm.get_byte_index(19, 1) == 1 * bm.get_row_stride() + (19 >> 3)
    assert bm.get_byte_index(19, 1) == 5


def test_get_byte_index_formula():
    bm = Bitmap(17, 4)
    assert bm.get_row_stride() == 3
    assert bm.get_byte_index(0, 0) == 0
    assert bm.get_byte_index(7, 0) == 0
    assert bm.get_byte_index(8, 0) == 1
    assert bm.get_byte_index(16, 0) == 2
    assert bm.get_byte_index(0, 1) == 3
    assert bm.get_byte_index(16, 3) == 3 * 3 + 2


def test_get_bit_offset():
    bm = Bitmap(64, 1)
    for x in range(64):
        assert bm.get_bit_offset(x) == x % 8


def test_set_byte_and_get_byte():
    bm = Bitmap(8, 1)
    bm.set_byte(0, 0xFF)
    assert bm.get_byte(0) == 0xFF
    for x in range(8):
        assert bm.get_pixel(x, 0) == 1
    # masking to 8 bits
    bm.set_byte(0, 0x1AB)
    assert bm.get_byte(0) == 0xAB


def test_get_byte_array_exposes_backing_store():
    bm = Bitmap(8, 1)
    arr = bm.get_byte_array()
    assert isinstance(arr, bytearray)
    bm.set_pixel(0, 0, 1)
    assert arr[0] == 0x80


def test_get_byte_out_of_bounds_raises():
    bm = Bitmap(8, 1)
    try:
        bm.get_byte(99)
    except IndexError:
        pass
    else:
        raise AssertionError("expected IndexError")


def test_fill_bitmap():
    bm = Bitmap(8, 3)
    bm.fill_bitmap(0xFF)
    for i in range(bm.get_length()):
        assert bm.get_byte(i) == 0xFF
    for y in range(3):
        for x in range(8):
            assert bm.get_pixel(x, y) == 1
    bm.fill_bitmap(0x00)
    for i in range(bm.get_length()):
        assert bm.get_byte(i) == 0x00


def test_get_bounds():
    bm = Bitmap(10, 5)
    assert bm.get_bounds() == (0, 0, 10, 5)


def test_equals_identical_bitmaps():
    a = Bitmap(10, 2)
    b = Bitmap(10, 2)
    a.set_pixel(3, 1, 1)
    b.set_pixel(3, 1, 1)
    assert a == b
    assert hash(a) == hash(b)


def test_equals_different_bytes_but_equal_pixels_in_pad():
    # width 12 -> rowStride 2, last byte holds only pixels 8..11 (4 used bits)
    a = Bitmap(12, 1)
    b = Bitmap(12, 1)
    # set identical real pixels
    a.set_pixel(0, 0, 1)
    b.set_pixel(0, 0, 1)
    # dirty the pad bits of b's last byte only (bits for x=12..15 don't exist)
    b.set_byte(1, 0x0F)  # 0000_1111 -> pixels x8..x11 = 0, pad bits set
    # real pixels x8..x11 are all 0 in both; pad differs but should be ignored
    assert a == b


def test_not_equals_on_real_pixel_difference():
    a = Bitmap(12, 1)
    b = Bitmap(12, 1)
    a.set_pixel(9, 0, 1)
    # b leaves x=9 unset
    assert a != b


def test_not_equals_different_dimensions():
    a = Bitmap(8, 2)
    b = Bitmap(8, 3)
    assert a != b


def test_not_equals_non_bitmap():
    a = Bitmap(8, 1)
    assert a != "not a bitmap"
    assert (a == 42) is False


def test_arraycopy():
    src = Bitmap(8, 2)
    src.set_byte(0, 0xAB)
    src.set_byte(1, 0xCD)
    dest = Bitmap(8, 2)
    Bitmap.arraycopy(src, 0, dest, 0, 2)
    assert dest.get_byte(0) == 0xAB
    assert dest.get_byte(1) == 0xCD


def test_arraycopy_partial_with_offset():
    src = Bitmap(8, 3)
    src.set_byte(0, 0x11)
    src.set_byte(1, 0x22)
    src.set_byte(2, 0x33)
    dest = Bitmap(8, 3)
    # copy 1 byte from src index 2 to dest index 1
    Bitmap.arraycopy(src, 2, dest, 1, 1)
    assert dest.get_byte(0) == 0x00
    assert dest.get_byte(1) == 0x33
    assert dest.get_byte(2) == 0x00
