import java.io.File;
import java.io.PrintStream;
import org.apache.fontbox.ttf.OS2WindowsMetricsTable;
import org.apache.fontbox.ttf.TrueTypeFont;
import org.apache.fontbox.ttf.TTFParser;
import org.apache.pdfbox.io.RandomAccessReadBufferedFile;

/**
 * Live oracle probe: emit Apache FontBox's parsed {@code OS/2} table fields in a
 * canonical line-oriented format that pypdfbox's OS2WindowsMetricsTable mirrors.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> Os2MetricsProbe font.ttf
 *
 * Output (UTF-8, stdout): one TAB-separated KEY\tVALUE line per accessor on
 * org.apache.fontbox.ttf.OS2WindowsMetricsTable. PANOSE is emitted as a
 * lower-case hex string of its 10 bytes. The version-gated fields (height,
 * capHeight, defaultChar, breakChar, maxContext for v>=2; codePageRange1/2 for
 * v>=1) are emitted verbatim — FontBox returns 0 for fields absent at the
 * table's declared version, so the probe surfaces whatever the accessor yields.
 */
public final class Os2MetricsProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        try (TrueTypeFont ttf = new TTFParser().parse(
                new RandomAccessReadBufferedFile(new File(args[0])))) {
            OS2WindowsMetricsTable os2 = ttf.getOS2Windows();
            if (os2 == null) {
                out.println("OS2\tabsent");
                return;
            }
            out.println("OS2\tpresent");
            out.println("version\t" + os2.getVersion());
            out.println("averageCharWidth\t" + os2.getAverageCharWidth());
            out.println("weightClass\t" + os2.getWeightClass());
            out.println("widthClass\t" + os2.getWidthClass());
            out.println("fsType\t" + os2.getFsType());
            out.println("subscriptXSize\t" + os2.getSubscriptXSize());
            out.println("subscriptYSize\t" + os2.getSubscriptYSize());
            out.println("subscriptXOffset\t" + os2.getSubscriptXOffset());
            out.println("subscriptYOffset\t" + os2.getSubscriptYOffset());
            out.println("superscriptXSize\t" + os2.getSuperscriptXSize());
            out.println("superscriptYSize\t" + os2.getSuperscriptYSize());
            out.println("superscriptXOffset\t" + os2.getSuperscriptXOffset());
            out.println("superscriptYOffset\t" + os2.getSuperscriptYOffset());
            out.println("strikeoutSize\t" + os2.getStrikeoutSize());
            out.println("strikeoutPosition\t" + os2.getStrikeoutPosition());
            out.println("familyClass\t" + os2.getFamilyClass());
            out.println("panose\t" + hex(os2.getPanose()));
            out.println("unicodeRange1\t" + os2.getUnicodeRange1());
            out.println("unicodeRange2\t" + os2.getUnicodeRange2());
            out.println("unicodeRange3\t" + os2.getUnicodeRange3());
            out.println("unicodeRange4\t" + os2.getUnicodeRange4());
            out.println("achVendId\t" + os2.getAchVendId());
            out.println("fsSelection\t" + os2.getFsSelection());
            out.println("firstCharIndex\t" + os2.getFirstCharIndex());
            out.println("lastCharIndex\t" + os2.getLastCharIndex());
            out.println("typoAscender\t" + os2.getTypoAscender());
            out.println("typoDescender\t" + os2.getTypoDescender());
            out.println("typoLineGap\t" + os2.getTypoLineGap());
            out.println("winAscent\t" + os2.getWinAscent());
            out.println("winDescent\t" + os2.getWinDescent());
            out.println("codePageRange1\t" + os2.getCodePageRange1());
            out.println("codePageRange2\t" + os2.getCodePageRange2());
            out.println("height\t" + os2.getHeight());
            out.println("capHeight\t" + os2.getCapHeight());
            out.println("defaultChar\t" + os2.getDefaultChar());
            out.println("breakChar\t" + os2.getBreakChar());
            out.println("maxContext\t" + os2.getMaxContext());
        }
    }

    private static String hex(byte[] b) {
        if (b == null) {
            return "null";
        }
        StringBuilder sb = new StringBuilder(b.length * 2);
        for (byte x : b) {
            sb.append(String.format("%02x", x & 0xFF));
        }
        return sb.toString();
    }
}
