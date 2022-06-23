#!/usr/bin/env python3
# Bully: Anniversary Edition import DDS to TEX
# Requires the BullyAE_parse.py script as well

# Usage:
#   -i | --input
#       Input file (Custom made .DDS)
#   -o | --output
#       Output file (Pre-existing .TEX)
#   BullyAE_DDS2TEX.py -i CustomFile.dds -o TargetFile.tex
# 
# Optional:
#   -c | --compress
#       Zlib compress the texture data
#   BullyAE_DDS2TEX.py -i CustomFile.dds -o TargetFile.tex -c

# Written by Edness    v1.2
# 2022-06-22  -  2022-06-23

import os, sys, zlib

try:
    from BullyAE_parse import parse_info
except ModuleNotFoundError:
    print("The BullyAE_parse.py script was not found!")
    sys.exit()

# Valid DDS bit-masks that can be generated by Paint.NET
# and can be easily converted to a format used by Bully:AE
RGBA32_MASK = (0xFF000000, 0x00FF0000, 0x0000FF00, 0x000000FF)  # R8G8B8A8
BGRA32_MASK = (0x0000FF00, 0x00FF0000, 0xFF000000, 0x000000FF)  # B8G8R8A8
RGB32_MASK  = (0xFF000000, 0x00FF0000, 0x0000FF00, 0x00000000)  # R8G8B8X8
BGR32_MASK  = (0x0000FF00, 0x00FF0000, 0xFF000000, 0x00000000)  # B8G8R8X8
BGR24_MASK  = (0x0000FF00, 0x00FF0000, 0xFF000000, 0x00000000)  # B8G8R8
BGRA16_MASK = (0x000F0000, 0xF0000000, 0x0F000000, 0x00F00000)  # B4G4R4A4
BGR16_MASK  = (0x00F80000, 0xE0070000, 0x1F000000, 0x00000000)  # B5G6R5
R8_MASK     = (0xFF000000, 0x00000000, 0x00000000, 0x00000000)  # R8
# DXT1, DXT3, DXT5 are also supported

def dds_to_tex(input, output, compress=False):
    assert(input and output)

    def read_int(bytes=0x4, endian="little"):
        return int.from_bytes(file.read(bytes), endian)

    def read_mask():
        return (read_int(endian="big"),
                read_int(endian="big"),
                read_int(endian="big"),
                read_int(endian="big"))

    def write_int(int, bytes=0x4):
        return int.to_bytes(bytes, "little")

    def tex_upd(key, value):
        return tex_info.replace(f"{key}={tex_dict.get(key)}".lower(), f"{key}={value}")

    print("Parsing DDS...")
    with open(input, "rb") as file:
        if file.read(0x4) != b"DDS ":
            print("Not a DDS file!")
            return

        file.seek(0xC)
        dds_height = read_int()
        dds_width = read_int()
        dds_data_size = read_int()
        file.seek(0x1C)
        dds_mips = read_int()

        file.seek(0x50)
        dds_fmt = read_int()
        dds_fmt_id = file.read(0x4)
        dds_bit_depth = read_int()

        if dds_fmt_id == bytes(4):
            dds_bit_mask = read_mask()
            if dds_bit_mask not in {
                8:  {R8_MASK},
                16: {BGRA16_MASK, BGR16_MASK},
                24: {BGR24_MASK},
                32: {RGBA32_MASK, BGRA32_MASK, RGB32_MASK, BGR32_MASK}
            }.get(dds_bit_depth):
                print("Unsupported DDS bit-mask:", " ".join([f"{x:08X}" for x in dds_bit_mask]))
                return

        elif dds_fmt_id not in {b"DXT1", b"DXT3", b"DXT5"}:
            print(f"Unsupported DDS format: {dds_fmt_id.decode()}")
            return

        file.seek(0x80)
        dds_data = list()
        dds_file_size = os.path.getsize(input)

        if dds_bit_depth == 16 and dds_bit_mask == BGRA16_MASK:
            while file.tell() < dds_file_size:
                clr_data = read_int(0x2)
                dds_data.extend(write_int((clr_data & 0x0FFF) << 4 | (clr_data & 0xF000) >> 12, 0x2))

        elif dds_bit_depth == 24:
            while file.tell() < dds_file_size:
                dds_data.extend(file.read(0x3)[::-1])

        elif dds_bit_depth == 32 and dds_bit_mask != RGBA32_MASK:
            if dds_bit_mask == BGRA32_MASK:
                while file.tell() < dds_file_size:
                    dds_data.extend(file.read(0x3)[::-1] + file.read(0x1))

            elif dds_bit_mask == BGR32_MASK:
                while file.tell() < dds_file_size:
                    dds_data.extend(file.read(0x3)[::-1])
                    file.seek(0x1, 1)
                dds_bit_depth = 24

            elif dds_bit_mask == RGB32_MASK:
                while file.tell() < dds_file_size:
                    dds_data.extend(file.read(0x3))
                    file.seek(0x1, 1)
                dds_bit_depth = 24

        else:
            dds_data.extend(file.read())

    dds_data = bytes(dds_data)
    if compress:
        dds_data = write_int(len(dds_data)) + zlib.compress(dds_data, level=9)

    print("Parsing TEX...")
    with open(output, "rb") as file:
        if read_int() != 7:
            print("Not a valid TEX format!")
            return

        tex_files = read_int()
        tex_hdr_unk = read_int()
        tex_info_ofs = read_int()

        file.seek(tex_info_ofs)
        tex_info = file.read(read_int()).decode()

    tex_dict = parse_info(tex_info)

    if dds_fmt_id == bytes(4):
        tex_fmt = {
            8:  8,
            24: 1,
            32: 0
        }.get(dds_bit_depth) if dds_bit_depth != 16 else (
            3 if dds_bit_mask == BGR16_MASK else 4)
    else:
        tex_fmt = {
            b"DXT1": 5,
            b"DXT3": 6,
            b"DXT5": 7
        }.get(dds_fmt_id)

    # I'm pretty sure this key isn't even used but just in case
    tex_info = tex_upd("mode", {
        0: "tm_raw32",
        1: "tm_standard",
        3: "tm_raw16",
        4: "tm_raw16",
        5: "tm_nopvr",
        6: "tm_nopvr",
        7: "tm_nopvr",
        8: "tm_singlechannel"  # "tm_distancefield" if it's a font
    }.get(tex_fmt))

    # Same with these two but as before - just in case
    tex_info = tex_upd("width", str(dds_width))
    tex_info = tex_upd("height", str(dds_height))

    # As with noMips, I've seen textures where this is set to true
    # but textures themselves have mips. Only compressOnDisk is used
    tex_info = tex_upd("nomips", ("false" if dds_mips > 1 else "true"))
    tex_info = tex_upd("compressondisk", "true" if compress else "false")

    with open(output, "wb") as file:
        file.write(write_int(0x7)
                 + write_int(0x2)
                 + write_int(tex_hdr_unk)
                 + write_int(0x18)
                 + write_int(tex_fmt)
                 + write_int(0x1C + len(tex_info))
                 + write_int(len(tex_info))
                 + tex_info.encode())

        file.write(write_int(tex_fmt)
                 + write_int(dds_width)
                 + write_int(dds_height)
                 + write_int(dds_mips)
                 + write_int(len(dds_data))
                 + dds_data)

    print(f"{os.path.split(output)} has been successfully updated!")

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--input", type=str, help="input file (DDS)")
    parser.add_argument("-o", "--output", type=str, help="output file (TEX)")
    parser.add_argument("-c", "--compress", action="store_true", help="compress the texture data")
    args = parser.parse_args()

    try: dds_to_tex(args.input, args.output, args.compress)
    except AssertionError: print("Insufficient arguments given. Use -h or --help to show valid arguments.")
    except FileNotFoundError: print("The provided file couldn't be found.")