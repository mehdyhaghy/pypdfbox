import java.io.PrintStream;
import java.nio.charset.StandardCharsets;
import java.util.Locale;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBoolean;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSStream;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.pdmodel.common.PDRectangle;
import org.apache.pdfbox.pdmodel.common.PDStream;
import org.apache.pdfbox.pdmodel.font.PDFontDescriptor;

/**
 * Differential fuzz probe for {@code PDFontDescriptor} malformed-dictionary
 * leniency, Apache PDFBox 3.0.7 (wave 1529, agent A).
 *
 * <h2>What this covers that the existing descriptor probes do not</h2>
 * {@code FontDescFlagsProbe} (wave 1468) drives a well-formed descriptor with a
 * clean {@code /Flags} integer + a full set of {@code COSFloat} metrics and
 * verifies the bit-predicate + metric-default surface. {@code FontDescProbe}
 * (wave 1412) reads descriptors off real embedded fonts. Neither fuzzes the
 * <em>COS type</em> of the dictionary entries. This probe builds deliberately
 * MALFORMED font descriptor dictionaries in memory and projects:
 * <ul>
 *   <li>{@code /Flags} missing / as COSFloat / as COSString / as huge int past
 *       the signed-32 range / negative — exercising Java int bit-extraction;</li>
 *   <li>{@code /FontBBox} missing / short (2,3 entries) / over-long (5) /
 *       non-numeric entries / a non-array shape;</li>
 *   <li>numeric metrics missing (default branch) and stored as non-numeric
 *       (COSString) shapes;</li>
 *   <li>{@code /FontName} missing / as a COSString (lenient) / as a COSInteger
 *       (rejected) / spec COSName;</li>
 *   <li>{@code /FontStretch} as name vs string; {@code /FontWeight} non-numeric;</li>
 *   <li>{@code /CharSet} absent / as COSString / as COSName (rejected);</li>
 *   <li>{@code /FontFile}{@code /FontFile2}{@code /FontFile3} presence as a
 *       stream vs a non-stream shape.</li>
 * </ul>
 *
 * <h2>Input</h2>
 * Deterministic, seed-free, no file I/O: a fixed inline corpus of descriptor
 * {@code COSDictionary}s built identically on both sides. The pypdfbox sibling
 * (tests/pdmodel/font/oracle/test_font_descriptor_fuzz_wave1529.py) rebuilds the
 * identical dicts and asserts each {@code CASE} line matches.
 *
 * <h2>Output grammar (one line per case)</h2>
 * <pre>
 *   CASE &lt;name&gt; flags=&lt;int&gt; pred=&lt;9 chars 0/1&gt;
 *        bbox=&lt;llx,lly,urx,ury|null&gt; metrics=&lt;12 floats csv&gt;
 *        name=&lt;str|null&gt; family=&lt;str|null&gt; stretch=&lt;str|null&gt;
 *        charset=&lt;str|null&gt; ff=&lt;0|1&gt; ff2=&lt;0|1&gt; ff3=&lt;0|1&gt;
 * </pre>
 * Floats are normalized to 4 decimals with -0.0 collapsed to 0.0.
 */
public final class FontDescriptorFuzzProbe {
    public static void main(String[] args) {
        PrintStream out =
                new PrintStream(System.out, true, StandardCharsets.UTF_8);

        emit(out, "flags_missing", caseFlagsMissing());
        emit(out, "flags_float", caseFlagsFloat());
        emit(out, "flags_float_trunc", caseFlagsFloatTrunc());
        emit(out, "flags_string", caseFlagsString());
        emit(out, "flags_bool", caseFlagsBool());
        emit(out, "flags_huge", caseFlagsHuge());
        emit(out, "flags_neg", caseFlagsNeg());
        emit(out, "flags_bit17_18_19", caseFlagsHighBits());
        emit(out, "bbox_missing", caseBBoxMissing());
        emit(out, "bbox_short2", caseBBoxShort2());
        emit(out, "bbox_short3", caseBBoxShort3());
        emit(out, "bbox_long5", caseBBoxLong5());
        emit(out, "bbox_nonnum", caseBBoxNonNum());
        emit(out, "bbox_nonarray", caseBBoxNonArray());
        emit(out, "metrics_missing", caseMetricsMissing());
        emit(out, "metrics_nonnum", caseMetricsNonNum());
        emit(out, "metrics_int", caseMetricsInt());
        emit(out, "capheight_negative", caseCapHeightNeg());
        emit(out, "name_missing", caseNameMissing());
        emit(out, "name_string", caseNameString());
        emit(out, "name_int", caseNameInt());
        emit(out, "stretch_string", caseStretchString());
        emit(out, "weight_nonnum", caseWeightNonNum());
        emit(out, "charset_absent", caseCharSetAbsent());
        emit(out, "charset_string", caseCharSetString());
        emit(out, "charset_name", caseCharSetName());
        emit(out, "fontfile_stream", caseFontFileStream());
        emit(out, "fontfile_nonstream", caseFontFileNonStream());
        emit(out, "all_three_fontfiles", caseAllThreeFontFiles());
    }

    // ---------------- case dictionaries ----------------

    private static COSDictionary base() {
        COSDictionary d = new COSDictionary();
        d.setItem(COSName.TYPE, COSName.getPDFName("FontDescriptor"));
        return d;
    }

    private static COSDictionary caseFlagsMissing() {
        COSDictionary d = base();
        d.setName(COSName.getPDFName("FontName"), "Probe");
        return d;
    }

    private static COSDictionary caseFlagsFloat() {
        COSDictionary d = base();
        // 64.0 -> FloatToInt should yield 64 (Italic).
        d.setItem(COSName.FLAGS, new COSFloat(64.0f));
        return d;
    }

    private static COSDictionary caseFlagsFloatTrunc() {
        COSDictionary d = base();
        // 65.9 truncates toward zero -> 65 = FixedPitch + Italic.
        d.setItem(COSName.FLAGS, new COSFloat(65.9f));
        return d;
    }

    private static COSDictionary caseFlagsString() {
        COSDictionary d = base();
        d.setItem(COSName.FLAGS, new COSString("64"));
        return d;
    }

    private static COSDictionary caseFlagsBool() {
        COSDictionary d = base();
        d.setItem(COSName.FLAGS, COSBoolean.TRUE);
        return d;
    }

    private static COSDictionary caseFlagsHuge() {
        COSDictionary d = base();
        // 0x1_0000_0040 wraps in signed-32 to 0x40 = 64 = Italic.
        d.setItem(COSName.FLAGS, COSInteger.get(0x100000040L));
        return d;
    }

    private static COSDictionary caseFlagsNeg() {
        COSDictionary d = base();
        // -1 = all bits set; reserved bits must not leak into named predicates.
        d.setInt(COSName.FLAGS, -1);
        return d;
    }

    private static COSDictionary caseFlagsHighBits() {
        COSDictionary d = base();
        d.setInt(COSName.FLAGS, (1 << 16) | (1 << 17) | (1 << 18));
        return d;
    }

    private static COSDictionary caseBBoxMissing() {
        COSDictionary d = base();
        d.setName(COSName.getPDFName("FontName"), "Probe");
        return d;
    }

    private static COSDictionary caseBBoxShort2() {
        COSDictionary d = base();
        COSArray a = new COSArray();
        a.add(new COSFloat(0f));
        a.add(new COSFloat(-200f));
        d.setItem(COSName.getPDFName("FontBBox"), a);
        return d;
    }

    private static COSDictionary caseBBoxShort3() {
        COSDictionary d = base();
        COSArray a = new COSArray();
        a.add(new COSFloat(0f));
        a.add(new COSFloat(-200f));
        a.add(new COSFloat(1000f));
        d.setItem(COSName.getPDFName("FontBBox"), a);
        return d;
    }

    private static COSDictionary caseBBoxLong5() {
        COSDictionary d = base();
        COSArray a = new COSArray();
        a.add(new COSFloat(0f));
        a.add(new COSFloat(-200f));
        a.add(new COSFloat(1000f));
        a.add(new COSFloat(900f));
        a.add(new COSFloat(123f));
        d.setItem(COSName.getPDFName("FontBBox"), a);
        return d;
    }

    private static COSDictionary caseBBoxNonNum() {
        COSDictionary d = base();
        COSArray a = new COSArray();
        a.add(new COSString("x"));
        a.add(new COSFloat(-200f));
        a.add(COSName.getPDFName("y"));
        a.add(new COSFloat(900f));
        d.setItem(COSName.getPDFName("FontBBox"), a);
        return d;
    }

    private static COSDictionary caseBBoxNonArray() {
        COSDictionary d = base();
        d.setInt(COSName.getPDFName("FontBBox"), 42);
        return d;
    }

    private static COSDictionary caseMetricsMissing() {
        COSDictionary d = base();
        d.setName(COSName.getPDFName("FontName"), "Probe");
        return d;
    }

    private static COSDictionary caseMetricsNonNum() {
        COSDictionary d = base();
        d.setItem(COSName.getPDFName("Ascent"), new COSString("700"));
        d.setItem(COSName.getPDFName("Descent"), COSName.getPDFName("low"));
        d.setItem(COSName.getPDFName("CapHeight"), new COSString("z"));
        d.setItem(COSName.getPDFName("StemV"), COSBoolean.FALSE);
        return d;
    }

    private static COSDictionary caseMetricsInt() {
        COSDictionary d = base();
        d.setInt(COSName.getPDFName("Ascent"), 718);
        d.setInt(COSName.getPDFName("Descent"), -207);
        d.setInt(COSName.getPDFName("CapHeight"), 662);
        d.setInt(COSName.getPDFName("StemV"), 84);
        d.setInt(COSName.getPDFName("FontWeight"), 700);
        return d;
    }

    private static COSDictionary caseCapHeightNeg() {
        COSDictionary d = base();
        // PDFBOX-429: negative CapHeight/XHeight read back as absolute value.
        d.setFloat(COSName.getPDFName("CapHeight"), -662f);
        d.setFloat(COSName.getPDFName("XHeight"), -450f);
        return d;
    }

    private static COSDictionary caseNameMissing() {
        COSDictionary d = base();
        return d;
    }

    private static COSDictionary caseNameString() {
        COSDictionary d = base();
        d.setItem(COSName.getPDFName("FontName"), new COSString("StringName"));
        return d;
    }

    private static COSDictionary caseNameInt() {
        COSDictionary d = base();
        d.setInt(COSName.getPDFName("FontName"), 7);
        return d;
    }

    private static COSDictionary caseStretchString() {
        COSDictionary d = base();
        d.setItem(COSName.getPDFName("FontStretch"), new COSString("Condensed"));
        d.setString(COSName.getPDFName("FontFamily"), "Probe Family");
        return d;
    }

    private static COSDictionary caseWeightNonNum() {
        COSDictionary d = base();
        d.setItem(COSName.getPDFName("FontWeight"), new COSString("bold"));
        return d;
    }

    private static COSDictionary caseCharSetAbsent() {
        COSDictionary d = base();
        return d;
    }

    private static COSDictionary caseCharSetString() {
        COSDictionary d = base();
        d.setItem(COSName.getPDFName("CharSet"), new COSString("/a/b/c"));
        return d;
    }

    private static COSDictionary caseCharSetName() {
        COSDictionary d = base();
        d.setItem(COSName.getPDFName("CharSet"), COSName.getPDFName("abc"));
        return d;
    }

    private static COSDictionary caseFontFileStream() {
        COSDictionary d = base();
        d.setItem(COSName.getPDFName("FontFile"), new COSStream());
        return d;
    }

    private static COSDictionary caseFontFileNonStream() {
        COSDictionary d = base();
        // A dictionary (not a stream) under /FontFile — getFontFile null-checks.
        d.setItem(COSName.getPDFName("FontFile"), new COSDictionary());
        return d;
    }

    private static COSDictionary caseAllThreeFontFiles() {
        COSDictionary d = base();
        d.setItem(COSName.getPDFName("FontFile"), new COSStream());
        d.setItem(COSName.getPDFName("FontFile2"), new COSStream());
        d.setItem(COSName.getPDFName("FontFile3"), new COSStream());
        return d;
    }

    // ---------------- projection ----------------

    private static void emit(PrintStream out, String name, COSDictionary dict) {
        PDFontDescriptor fd = new PDFontDescriptor(dict);
        StringBuilder sb = new StringBuilder("CASE\t").append(name);
        sb.append("\tflags=").append(fd.getFlags());
        sb.append("\tpred=")
                .append(b(fd.isFixedPitch()))
                .append(b(fd.isSerif()))
                .append(b(fd.isSymbolic()))
                .append(b(fd.isScript()))
                .append(b(fd.isNonSymbolic()))
                .append(b(fd.isItalic()))
                .append(b(fd.isAllCap()))
                .append(b(fd.isSmallCap()))
                .append(b(fd.isForceBold()));

        PDRectangle bbox = fd.getFontBoundingBox();
        if (bbox == null) {
            sb.append("\tbbox=null");
        } else {
            sb.append("\tbbox=")
                    .append(fmt(bbox.getLowerLeftX())).append(',')
                    .append(fmt(bbox.getLowerLeftY())).append(',')
                    .append(fmt(bbox.getUpperRightX())).append(',')
                    .append(fmt(bbox.getUpperRightY()));
        }

        sb.append("\tmetrics=")
                .append(fmt(fd.getItalicAngle())).append(',')
                .append(fmt(fd.getAscent())).append(',')
                .append(fmt(fd.getDescent())).append(',')
                .append(fmt(fd.getCapHeight())).append(',')
                .append(fmt(fd.getXHeight())).append(',')
                .append(fmt(fd.getStemV())).append(',')
                .append(fmt(fd.getStemH())).append(',')
                .append(fmt(fd.getMissingWidth())).append(',')
                .append(fmt(fd.getLeading())).append(',')
                .append(fmt(fd.getAverageWidth())).append(',')
                .append(fmt(fd.getMaxWidth())).append(',')
                .append(fmt(fd.getFontWeight()));

        sb.append("\tname=").append(str(fd.getFontName()));
        sb.append("\tfamily=").append(str(fd.getFontFamily()));
        sb.append("\tstretch=").append(str(fd.getFontStretch()));
        sb.append("\tcharset=").append(str(fd.getCharSet()));

        sb.append("\tff=").append(present(fd.getFontFile()));
        sb.append("\tff2=").append(present(fd.getFontFile2()));
        sb.append("\tff3=").append(present(fd.getFontFile3()));

        out.println(sb);
    }

    private static int b(boolean v) {
        return v ? 1 : 0;
    }

    private static int present(PDStream s) {
        return s == null ? 0 : 1;
    }

    private static String str(String s) {
        return s == null ? "null" : s;
    }

    private static String fmt(float v) {
        if (v == 0.0f) {
            v = 0.0f;
        }
        return String.format(Locale.ROOT, "%.4f", v);
    }
}
