import java.io.PrintStream;
import java.util.Locale;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.font.PDFontDescriptor;

/**
 * Live oracle probe: build a PDFontDescriptor from a synthetic COSDictionary
 * with a chosen /Flags integer plus a full set of numeric metrics, then emit
 * every /Flags bit-predicate (PDF 32000-1 §9.8.2 Table 121) and every numeric
 * metric accessor as a canonical line-oriented block. Companion to
 * FontDescProbe (wave 1412, descriptor read off real fonts); this probe
 * (wave 1468) isolates the FLAGS bit-decode + metric-default surface by
 * driving the wrapper directly so a divergence pins to the predicate logic,
 * not to font-program parsing.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> FontDescFlagsProbe <flagsInt> <withMetrics 0|1>
 *
 * Output (UTF-8, stdout):
 *   FLAGS\t<flagsInt>
 *   PRED\tfixedPitch=<0|1>\tserif=..\tsymbolic=..\tscript=..\tnonSymbolic=..
 *        \titalic=..\tallCap=..\tsmallCap=..\tforceBold=..
 *   METRIC\titalicAngle=<f>\tascent=..\tdescent=..\tcapHeight=..\txHeight=..
 *        \tstemV=..\tstemH=..\tmissingWidth=..\tleading=..\tavgWidth=..
 *        \tmaxWidth=..\tfontWeight=..
 * Floats are normalized to 4 decimals with -0.0 collapsed to 0.0.
 * When withMetrics==0 no metric keys are set so every getter returns its
 * default (verifies the default branch of each accessor).
 */
public final class FontDescFlagsProbe {
    public static void main(String[] args) {
        PrintStream out = new PrintStream(System.out, true, java.nio.charset.StandardCharsets.UTF_8);
        int flags = Integer.parseInt(args[0]);
        boolean withMetrics = args.length > 1 && "1".equals(args[1]);

        COSDictionary dict = new COSDictionary();
        dict.setItem(COSName.TYPE, COSName.getPDFName("FontDescriptor"));
        dict.setName(COSName.getPDFName("FontName"), "ProbeFont");
        dict.setInt(COSName.FLAGS, flags);
        if (withMetrics) {
            dict.setFloat(COSName.getPDFName("ItalicAngle"), -12.5f);
            dict.setFloat(COSName.getPDFName("Ascent"), 718.0f);
            dict.setFloat(COSName.getPDFName("Descent"), -207.0f);
            dict.setFloat(COSName.getPDFName("CapHeight"), 662.0f);
            dict.setFloat(COSName.getPDFName("XHeight"), 450.0f);
            dict.setFloat(COSName.getPDFName("StemV"), 84.0f);
            dict.setFloat(COSName.getPDFName("StemH"), 73.0f);
            dict.setFloat(COSName.getPDFName("MissingWidth"), 250.0f);
            dict.setFloat(COSName.getPDFName("Leading"), 33.0f);
            dict.setFloat(COSName.getPDFName("AvgWidth"), 441.0f);
            dict.setFloat(COSName.getPDFName("MaxWidth"), 1000.0f);
            dict.setFloat(COSName.getPDFName("FontWeight"), 400.0f);
        }

        PDFontDescriptor fd = new PDFontDescriptor(dict);

        StringBuilder sb = new StringBuilder();
        sb.append("FLAGS\t").append(fd.getFlags()).append('\n');
        sb.append("PRED")
                .append("\tfixedPitch=").append(b(fd.isFixedPitch()))
                .append("\tserif=").append(b(fd.isSerif()))
                .append("\tsymbolic=").append(b(fd.isSymbolic()))
                .append("\tscript=").append(b(fd.isScript()))
                .append("\tnonSymbolic=").append(b(fd.isNonSymbolic()))
                .append("\titalic=").append(b(fd.isItalic()))
                .append("\tallCap=").append(b(fd.isAllCap()))
                .append("\tsmallCap=").append(b(fd.isSmallCap()))
                .append("\tforceBold=").append(b(fd.isForceBold()))
                .append('\n');
        sb.append("METRIC")
                .append("\titalicAngle=").append(fmt(fd.getItalicAngle()))
                .append("\tascent=").append(fmt(fd.getAscent()))
                .append("\tdescent=").append(fmt(fd.getDescent()))
                .append("\tcapHeight=").append(fmt(fd.getCapHeight()))
                .append("\txHeight=").append(fmt(fd.getXHeight()))
                .append("\tstemV=").append(fmt(fd.getStemV()))
                .append("\tstemH=").append(fmt(fd.getStemH()))
                .append("\tmissingWidth=").append(fmt(fd.getMissingWidth()))
                .append("\tleading=").append(fmt(fd.getLeading()))
                .append("\tavgWidth=").append(fmt(fd.getAverageWidth()))
                .append("\tmaxWidth=").append(fmt(fd.getMaxWidth()))
                .append("\tfontWeight=").append(fmt(fd.getFontWeight()))
                .append('\n');
        out.print(sb);
    }

    private static int b(boolean v) {
        return v ? 1 : 0;
    }

    private static String fmt(float v) {
        if (v == 0.0f) {
            v = 0.0f;
        }
        return String.format(Locale.ROOT, "%.4f", v);
    }
}
