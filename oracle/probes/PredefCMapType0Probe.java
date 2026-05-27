import java.io.ByteArrayInputStream;
import java.io.PrintStream;
import org.apache.fontbox.cmap.CMap;
import org.apache.fontbox.cmap.CMapParser;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.font.PDType0Font;

/**
 * Live oracle probe: predefined CJK CMaps used by a Type0/CID font.
 *
 * Usage:
 *   java PredefCMapType0Probe cmap   <name>     <hexcode> ...
 *   java PredefCMapType0Probe type0  <cmapName> <hexcode> ...
 *
 * Mode "cmap" loads the predefined CMap directly via
 * CMapParser.parsePredefined and, for each big-endian hex code, emits the
 * codespace-assigned readCode length and toCID:
 *   CMAP <name>
 *   WMODE <wmode>
 *   CID <hexcode> -> <cid> len=<codeLength>
 *
 * Mode "type0" builds a minimal Type0 font dictionary referencing a
 * descendant CIDFontType2 (Adobe-GB1) with /Encoding set to the predefined
 * CMap name, wraps it with PDType0Font, and emits PDType0Font.codeToCID for
 * each code (the font-level path, distinct from the raw CMap.toCID path):
 *   TYPE0 <cmapName>
 *   WMODE <wmode>
 *   CODETOCID <hexcode> -> <cid> len=<codeLength>
 */
public final class PredefCMapType0Probe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        String mode = args[0];
        String name = args[1];
        if ("cmap".equals(mode)) {
            CMap cmap = new CMapParser().parsePredefined(name);
            out.println("CMAP " + cmap.getName());
            out.println("WMODE " + cmap.getWMode());
            for (int i = 2; i < args.length; i++) {
                byte[] code = hexToBytes(args[i]);
                int cid = cmap.toCID(toInt(code));
                int len = codeLength(cmap, code);
                out.println("CID " + args[i].toUpperCase() + " -> " + cid
                        + " len=" + len);
            }
        } else if ("type0".equals(mode)) {
            try (PDDocument doc = new PDDocument()) {
                PDType0Font font = buildType0(name);
                out.println("TYPE0 " + name);
                out.println("WMODE " + (font.isVertical() ? 1 : 0));
                for (int i = 2; i < args.length; i++) {
                    byte[] code = hexToBytes(args[i]);
                    int value = toInt(code);
                    int cid = font.codeToCID(value);
                    int len = readLen(font, code);
                    out.println("CODETOCID " + args[i].toUpperCase() + " -> "
                            + cid + " len=" + len);
                }
            }
        } else {
            throw new IllegalArgumentException("unknown mode: " + mode);
        }
    }

    /** Build a Type0 font dict over an Adobe-GB1 CIDFontType2 descendant. */
    private static PDType0Font buildType0(String cmapName) throws Exception {
        COSDictionary cidSysInfo = new COSDictionary();
        cidSysInfo.setString(COSName.REGISTRY, "Adobe");
        cidSysInfo.setString(COSName.ORDERING, "GB1");
        cidSysInfo.setInt(COSName.SUPPLEMENT, 5);

        COSDictionary descendant = new COSDictionary();
        descendant.setItem(COSName.TYPE, COSName.FONT);
        descendant.setItem(COSName.SUBTYPE, COSName.getPDFName("CIDFontType2"));
        descendant.setName(COSName.BASE_FONT, "STSong-Light");
        descendant.setItem(COSName.CIDSYSTEMINFO, cidSysInfo);

        COSArray descendants = new COSArray();
        descendants.add(descendant);

        COSDictionary type0 = new COSDictionary();
        type0.setItem(COSName.TYPE, COSName.FONT);
        type0.setItem(COSName.SUBTYPE, COSName.TYPE0);
        type0.setName(COSName.BASE_FONT, "STSong-Light-" + cmapName);
        type0.setName(COSName.ENCODING, cmapName);
        type0.setItem(COSName.DESCENDANT_FONTS, descendants);

        return (PDType0Font) PDType0Font.class
                .getDeclaredConstructor(COSDictionary.class)
                .newInstance(type0);
    }

    /** Number of bytes CMap.readCode consumes from the buffer. */
    private static int codeLength(CMap cmap, byte[] code) throws Exception {
        ByteArrayInputStream in = new ByteArrayInputStream(code);
        int before = in.available();
        cmap.readCode(in);
        return before - in.available();
    }

    /** Number of bytes PDType0Font.readCode consumes from the buffer. */
    private static int readLen(PDType0Font font, byte[] code) throws Exception {
        ByteArrayInputStream in = new ByteArrayInputStream(code);
        int before = in.available();
        font.readCode(in);
        return before - in.available();
    }

    private static int toInt(byte[] data) {
        int code = 0;
        for (byte b : data) {
            code = (code << 8) | (b & 0xFF);
        }
        return code;
    }

    private static byte[] hexToBytes(String hex) {
        int n = hex.length() / 2;
        byte[] out = new byte[n];
        for (int i = 0; i < n; i++) {
            out[i] = (byte) Integer.parseInt(hex.substring(i * 2, i * 2 + 2), 16);
        }
        return out;
    }
}
