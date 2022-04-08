# Todo:
#   * Bones
#   * Weird edge case models (e.g. dduvet.msh)
#   * Remaining mesh type assignments
#       * Especially Normals
#       * I've only seen Assignment 7 once so far in cube.msh
#   * Handle duplicate textures/materials (?)

# Written by Edness
# 2022-04-08   v1.0

from inc_noesis import *

def registerNoesisTypes():
    handleTex = noesis.register("Bully: Anniversary Edition Textures", ".tex")
    noesis.setHandlerTypeCheck(handleTex, aeTexCheckType)
    noesis.setHandlerLoadRGBA(handleTex, aeTexLoadTexture)

    handleMsh = noesis.register("Bully: Anniversary Edition Models", ".msh")
    noesis.setHandlerTypeCheck(handleMsh, aeMshCheckType)
    noesis.setHandlerLoadModel(handleMsh, aeMshLoadModel)
    return 1

def aeTexCheckType(data):
    chk = NoeBitStream(data)
    if chk.readUInt() == 0x7:
        return 1
    return 0

def aeMshCheckType(data):
    chk = NoeBitStream(data)
    if 0x6 <= chk.readUInt() <= 0xC:
        return 1
    return 0




class AeParseHeader:
    def __init__(self, hdr):
        self.fileVer = hdr.readUInt()
        self.fileCnt = hdr.readUInt() - 1
        hdr.seek(0xC)
        self.infoOfs = hdr.readUInt()

        self.fileFmt = list()
        self.fileOfs = list()
        for i in range(self.fileCnt):
            self.fileFmt.append(hdr.readUInt())
            self.fileOfs.append(hdr.readUInt())

def aeTxtParse(txt):
    # Converts strings to a functional Python dict or list

    tryOrder = (int, float, str)
    def tryStep(name):
        for step in tryOrder:
            try:
                step(name)
                return step
            except:
                continue

    def fixEval(txt):
        def fixList(lst):
            if lst[0] == len(lst) - 1:
                lst = lst[1:]
            for itm in lst:
                if type(itm) is list:
                    itm = fixList(itm)
                elif type(itm) is dict:
                    itm = fixDict(itm)
            return lst

        def fixDict(dct):
            for i in dct:
                if type(dct[i]) is list:
                    dct[i] = fixList(dct[i])
                elif type(dct[i]) is dict:
                    dct[i] = fixDict(dct[i])
            return dct

        if type(txt) is list:
            txt = fixList(txt)
        elif type(txt) is dict:
            txt = fixDict(txt)
        return txt

    txt = txt.replace("\\", "\\\\")
    txt = txt.replace("\t", "")
    txt = txt.replace("\n", "")

    txt = txt.split(",")
    for i in range(len(txt)):
        ln = txt[i].split("=")
        for j in range(len(ln)):
            lnMain = ln[j]
            skipStart = 0
            skipEnd = len(ln[j])
            while lnMain.startswith(("{", "[")):
                lnMain = lnMain[1:]
                skipStart += 1
            while lnMain.endswith(("}", "]")):
                lnMain = lnMain[:-1]
                skipEnd -= 1
            if tryStep(lnMain) is str:
                if not lnMain.startswith(("\"", "\'")) and not lnMain.endswith(("\"", "\'")):
                    lnMain = "\"{}\"".format(lnMain)
                    if lnMain == "\"\"":
                        lnMain = "None"
                    elif lnMain.lower() == "\"true\"":
                        lnMain = "True"
                    elif lnMain.lower() == "\"false\"":
                        lnMain = "False"
            ln[j] = ln[j][:skipStart] + lnMain + ln[j][skipEnd:]
        txt[i] = ":".join(ln)
    txt = eval(",".join(txt))
    return fixEval(txt)

def aeTxtDecrypt(txt):
    # Python reimplementation of Bartlomiej Duda's  Bully_XML_Tool.cpp  script
    # see  BullyAE_decrypt.py  for the standalone version

    aeKey = b"6Ev2GlK1sWoCa5MfQ0pj43DH8Rzi9UnX"
    aeHash = 0x0CEB538D

    encSize = len(txt)
    decSize = (5 * encSize >> 3)
    decData = list(bytes(decSize + 1))

    aeBuffer = list(bytes(256))
    for idx in range(len(aeKey)):
        aeBuffer[aeKey[idx]] = idx

    case = 0
    bufIdx = 0
    for i in range(encSize):
        char = aeBuffer[txt[i]]

        next = {
            4: char << 7,
            5: char << 6,
            6: char << 5,
            7: char << 4
        }.get(case, 0)

        char = {
            0: char << 3,
            1: char << 2,
            2: char << 1,
            3: char,
            4: char >> 1,
            5: char >> 2,
            6: char >> 3,
            7: char >> 4
        }.get(case)

        decData[bufIdx] |= char
        decData[bufIdx + 1] |= next

        if (case + 5) % 8 < case:
            bufIdx += 1
        case = (case + 5) % 8

    xor = 18
    for i in range(decSize):
        aeHash = 0xAB * (aeHash % 0xB1) - 2 * (aeHash // 0xB1) & 0xFFFFFFFF
        decData[i] = ((decData[i] ^ xor) + aeHash) & 0xFF
        xor += 6

    return noeStrFromBytes(bytes(decData[:-1]))

def aeTexLoadTexture(data, texList, extName=None):
    tex = NoeBitStream(data)
    hdr = AeParseHeader(tex)
    rapi.processCommands("-texnorepfn")

    tex.seek(hdr.infoOfs)
    strSize = tex.readUInt()
    hdrInfo = aeTxtParse(noeStrFromBytes(tex.readBytes(strSize)))

    intPath = hdrInfo.get("importfilepath")
    intName = os.path.splitext(os.path.basename(intPath))[0]
    if extName is None:
        extName = os.path.splitext(os.path.basename(rapi.getInputName()))[0]
    if extName != intName and intName != "":
        if extName.lower() == intName.lower():
            texName = intName
        else:
            texName = "{} ({})".format(extName, intName)
    else:
        texName = extName

    for i in range(hdr.fileCnt):
        tex.seek(hdr.fileOfs[i])
        # partially taken, rewritten & improved upon AuraShadow's  tex_BullyAnniversaryEdition_Android_iOS_tex.py  script

        texFmt = tex.readUInt() # == hdr.fileFmt[i]  ...most of the times, at least
        texWidth = tex.readUInt()
        texHeight = tex.readUInt()
        texUnk = tex.readUInt()
        texSize = tex.readUInt()
        if hdrInfo.get("compressondisk") == True:
            decSize = tex.readUInt()
            texData = rapi.decompInflate(tex.readBytes(texSize - 4), decSize)
        else:
            texData = tex.readBytes(texSize)

        # DATA TYPES
        #  0  =  RGBA-8888
        #  1  =  RGB-888
        #  3  =  BGR-565
        #  4  =  ABGR-4444
        #  5  =  DXT1 / BC1
        #  6  =  DXT3 / BC2
        #  7  =  DXT5 / BC3
        #  8  =  A-8
        #  9  =  PVRTC2

        texType = noesis.NOESISTEX_RGBA32 # texFmt == 0, also used for 3, 4, 8, and 9
        if texFmt == 1:
            texType = noesis.NOESISTEX_RGB24
        elif texFmt == 3:
            texData = rapi.imageDecodeRaw(texData, texWidth, texHeight, "B5G6R5")
        elif texFmt == 4:
            texData = rapi.imageDecodeRaw(texData, texWidth, texHeight, "A4B4G4R4")
        elif texFmt == 5:
            texType = noesis.NOESISTEX_DXT1
        elif texFmt == 6:
            texType = noesis.NOESISTEX_DXT3
        elif texFmt == 7:
            texType = noesis.NOESISTEX_DXT5
        elif texFmt == 8:
            texData = rapi.imageDecodeRaw(texData, texWidth, texHeight, "A8")
        elif texFmt == 9:
            texData = rapi.imageDecodePVRTC(texData, texWidth, texHeight, 4, noesis.PVRTC_DECODE_PVRTC2_ROTATE_BLOCK_PAL)
        elif texFmt:
            noesis.doException("Unhandled texture format {}".format(texFmt))
        texList.append(NoeTexture(texName if hdr.fileCnt == 1 else "{} (Texture {})".format(texName, i + 1), texWidth, texHeight, texData, texType))
    if intPath:
        print("Internal name:", intPath)
    return hdr.fileCnt, texName

def aeMshLoadModel(data, mdlList):
    msh = NoeBitStream(data)
    hdr = AeParseHeader(msh)
    rapi.processCommands("-rotate 90 0 0")
    rapi.rpgCreateContext()

    # DATA TYPES
    #  1  =  Two Floats
    #  2  =  Three Floats
    #  8  =  ???   bone weight/idx?
    #  9  =  ???   bone weight/idx?
    # 10  =  ???   Something 8-bit x 4, last byte unused?
    # 11  =  Normalised 12(11?)-bit (2048)

    def mshDataParse(mshData=[]):
        if mshType == 1:
            mshData.extend(msh.readBytes(8))
        elif mshType == 2:
            mshData.extend(msh.readBytes(12))
        elif 8 <= mshType <= 10:
            msh.seek(0x4, 1)
        #elif mshType == 8:
        #    mshData.extend(msh.readBytes(4))
        #elif mshType == 9:
        #    mshData.extend(msh.readBytes(4))
        #elif mshType == 10:
        #    mshData.extend(struct.pack("<f", msh.readByte() / 255))
        #    mshData.extend(struct.pack("<f", msh.readByte() / 255))
        #    mshData.extend(struct.pack("<f", msh.readByte() / 255))
        #    msh.seek(0x1, 1)
        elif mshType == 11:
            mshData.extend(struct.pack("<f", msh.readShort() / 2048))
            mshData.extend(struct.pack("<f", msh.readShort() / 2048))
        else:
            noesis.doException("Unhandled mesh data type {}".format(mshType))

    def mshTexLoad(idx):
        texName = texNames[idx]
        texPath = basePath + texName + ".tex"
        try:
            with open(texPath, "rb") as tex:
                texCnt, texName = aeTexLoadTexture(tex.read(), texList, texName)
            print("Successfully loaded {}.tex".format(texName))
            return texName + ("" if texCnt < 2 else " (Texture 2)")
        except Exception as aeExc:
            print("Failed loading {}.tex: {}".format(texName, aeExc))
            return ""

    basePath = os.path.split(rapi.getInputName())[0] + "\\"
    boneList = list()
    matList = list()
    texList = list()

    msh.seek(hdr.infoOfs)
    mtlCnt = msh.readUInt()
    mtlNames = list()
    for i in range(mtlCnt):
        strSize = msh.readUInt()
        mtlNames.append(noeStrFromBytes(msh.readBytes(strSize)))
    boneCnt = msh.readUInt()
    for i in range(boneCnt):
        strSize = msh.readUInt()
        boneName = noeStrFromBytes(msh.readBytes(strSize))
        boneMat = NoeMat43.fromBytes(msh.readBytes(48))
        boneIdx = msh.readInt()
        #boneList.append(NoeBone(boneIdx, boneName, boneMat))
    msh.seek(0x1, 1) # the size changes depending on hdr.fileVer

    for i in range(hdr.fileCnt):
        msh.seek(hdr.fileOfs[i])
        mshCnt = msh.readUInt()
        if not mshCnt:
            break
        for j in range(mshCnt):
            strSize = msh.readUInt()
            mshName = noeStrFromBytes(msh.readBytes(strSize))
            rapi.rpgSetName(mshName)
            msh.seek(0x2, 1)
            vertCnt = msh.readUInt()
            # most of the times varying amounts of null, occasionally floats
            while not vertCnt or vertCnt > 0xFFFF:
                vertCnt = msh.readUInt()
            faceCnt = msh.readUInt()

            print("Faces offset: 0x{:X}".format(msh.tell()))
            triData = msh.readBytes(faceCnt * 2)

            mshInfoCnt = msh.readUInt()
            mshInfo = list()
            for k in range(mshInfoCnt):
                mshInfo.append([msh.readUInt() for l in range(2)][::-1])
                msh.seek(0x2, 1)
            print("Vertices offset: 0x{:X}".format(msh.tell()))
            print("Block layout:", mshInfo)

            # DATA ASSIGNMENTS
            #  0  =  Vertices
            #  1  =  
            #  2  =  
            #  3  =  
            #  4  =  UVs
            #  5  =  Normals?
            #  6  =  
            #  7  =  

            uvData = list()
            nrmData = list()
            vertData = list()
            for k in range(vertCnt):
                for mshAssign, mshType in mshInfo:
                    if mshAssign == 0:
                        mshDataParse(vertData)
                    elif mshAssign == 4:
                        mshDataParse(uvData)
                    elif mshAssign == 5:
                        mshDataParse(nrmData)
                    elif 1 <= mshAssign <= 7:
                        mshDataParse()
                    else:
                        noesis.doException("Unhandled mesh data assignment {}".format(mshAssign))

            rapi.rpgBindPositionBuffer(bytes(vertData), noesis.RPGEODATA_FLOAT, 12)
            if uvData:
                rapi.rpgBindUV1Buffer(bytes(uvData), noesis.RPGEODATA_FLOAT, 8)
            #if nrmData:
            #    for b in nrmData: print("{:02X}".format(b), end=" ")
            #    rapi.rpgBindNormalBuffer(bytes(nrmData), noesis.RPGEODATA_FLOAT, 12)

            mshSubCnt = msh.readUInt()
            for k in range(mshSubCnt):
                mshSubStart = msh.readUInt() * 2
                mshSubSize = msh.readUInt()
                mtlIdx = msh.readUInt()
                msh.seek(0x4, 1)

                mtlPath = basePath + mtlNames[mtlIdx] + ".mtl"
                try:
                    with open(mtlPath, "rb") as mtl:
                        assert(mtl.read(0x2) == b"Wx")
                        mtlInfo = aeTxtParse(aeTxtDecrypt(mtl.read()))
                        print("Successfully loaded {}.mtl".format(mtlNames[mtlIdx]))
                except Exception as aeExc:
                    print("Failed loading {}.mtl: {}".format(mtlNames[mtlIdx], aeExc))
                    continue

                texType = mtlInfo.get("effect(effect)")
                texNames = mtlInfo.get("textures(orderedarray<texture2d>)")
                print(texType, texNames)

                rapi.rpgSetMaterial(mtlNames[mtlIdx])
                rapi.rpgSetName(mshName + mtlNames[mtlIdx][3:])
                mat = NoeMaterial(mtlNames[mtlIdx], mshTexLoad(0))
                texIdx = 1
                if "normal" in texType:
                    # is it  setBumpTexture  or  setNormalTexture?
                    mat.setBumpTexture(mshTexLoad(1))
                    texIdx += 1
                if "spec" in texType:
                    mat.setSpecularTexture(mshTexLoad(texIdx))
                if mtlInfo.get("doublesided(bool)") == True:
                    mat.setFlags(noesis.NMATFLAG_TWOSIDED)
                #if mtlInfo.get("alphatest(bool)"):
                #    mat.setAlphaTest(0)
                matList.append(mat)

                rapi.rpgCommitTriangles(triData[mshSubStart:][:mshSubSize * 2], noesis.RPGEODATA_USHORT, mshSubSize, noesis.RPGEO_TRIANGLE)

        #rapi.setPreviewOption("setAngOfs", "0 -90 90")
        mdl = rapi.rpgConstructModel()
        mdl.setModelMaterials(NoeModelMaterials(texList, matList))
        mdl.setBones(boneList)
        mdlList.append(mdl)
    return 1