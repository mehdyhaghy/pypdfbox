import java.io.OutputStream;
import java.io.PrintStream;
import java.nio.charset.StandardCharsets;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSStream;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.pdmodel.common.PDStream;
import org.apache.pdfbox.pdmodel.font.PDFontDescriptor;

/**
 * Differential fuzz probe for embedded-font-program extraction from a
 * {@code PDFontDescriptor}, Apache PDFBox 3.0.7 (wave 1565, agent C).
 *
 * <h2>What this covers that the existing descriptor probes do not</h2>
 * {@code FontDescriptorFuzzProbe} (wave 1529) fuzzes the COS-type leniency of
 * descriptor metric/name entries and projects only the <em>presence</em> (0/1)
 * of the three font-file slots — it never reads the embedded program bytes.
 * {@code Type1EmbedProbe} / {@code SubsetEmbedProbe} parse a whole embedded
 * font through FontBox from a real PDF. Neither projects the descriptor-level
 * <em>byte length</em> of the extracted program, the {@code /FontFile3}
 * {@code /Subtype} discriminator (Type1C vs OpenType vs CIDFontType0C), or the
 * decoded-vs-encoded length when the program is FlateDecode-compressed.
 *
 * This probe builds descriptors in memory whose font-file slots hold actual
 * embedded program bytes (synthetic Type1 PFB / TrueType / CFF magic) — some
 * raw, some FlateDecode-encoded, some with {@code /Length1}{@code /Length2}
 * {@code /Length3} segment metadata, some non-stream / absent — and projects:
 * <ul>
 *   <li>which slot is populated ({@code ff}/{@code ff2}/{@code ff3} 0/1);</li>
 *   <li>{@code isEmbedded}: any program present;</li>
 *   <li>the <em>decoded</em> byte length of each present program via
 *       {@code PDStream.toByteArray().length} (-1 when absent);</li>
 *   <li>the {@code /FontFile3} {@code /Subtype} name (or {@code null});</li>
 *   <li>{@code /Length1}{@code /Length2}{@code /Length3} on {@code /FontFile}
 *       (the Type1 clear/encrypted/fixed segment sizes; -1 when absent).</li>
 * </ul>
 *
 * <h2>Input</h2>
 * Deterministic, seed-free, no file I/O: a fixed inline corpus rebuilt
 * identically on both sides. The pypdfbox sibling
 * (tests/pdmodel/font/oracle/test_embedded_font_program_fuzz_wave1565.py)
 * reconstructs the same dicts and asserts each {@code CASE} line matches.
 *
 * <h2>Output grammar (one line per case)</h2>
 * <pre>
 *   CASE &lt;name&gt; ff=&lt;0|1&gt; ff2=&lt;0|1&gt; ff3=&lt;0|1&gt; emb=&lt;0|1&gt;
 *        len=&lt;int&gt; len2=&lt;int&gt; len3=&lt;int&gt; sub=&lt;str|null&gt;
 *        l1=&lt;int&gt; l2=&lt;int&gt; l3=&lt;int&gt;
 * </pre>
 * {@code len}/{@code len2}/{@code len3} are the decoded byte lengths of
 * {@code /FontFile}/{@code /FontFile2}/{@code /FontFile3} (-1 = slot absent).
 */
public final class EmbeddedFontProgramFuzzProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out =
                new PrintStream(System.out, true, StandardCharsets.UTF_8);

        emit(out, "none", caseNone());
        emit(out, "ff1_type1_raw", caseFf1Type1Raw());
        emit(out, "ff1_type1_seglen", caseFf1Type1SegLen());
        emit(out, "ff1_type1_flate", caseFf1Type1Flate());
        emit(out, "ff1_empty_stream", caseFf1EmptyStream());
        emit(out, "ff1_nonstream_dict", caseFf1NonStreamDict());
        emit(out, "ff1_nonstream_name", caseFf1NonStreamName());
        emit(out, "ff2_ttf_raw", caseFf2TtfRaw());
        emit(out, "ff2_ttf_flate", caseFf2TtfFlate());
        emit(out, "ff2_otto_raw", caseFf2OttoRaw());
        emit(out, "ff2_truncated", caseFf2Truncated());
        emit(out, "ff2_nonstream", caseFf2NonStream());
        emit(out, "ff3_type1c", caseFf3Type1c());
        emit(out, "ff3_opentype", caseFf3OpenType());
        emit(out, "ff3_cidfonttype0c", caseFf3CidFontType0c());
        emit(out, "ff3_no_subtype", caseFf3NoSubtype());
        emit(out, "ff3_subtype_string", caseFf3SubtypeString());
        emit(out, "ff3_flate", caseFf3Flate());
        emit(out, "ff3_corrupt_short", caseFf3CorruptShort());
        emit(out, "ff3_nonstream", caseFf3NonStream());
        emit(out, "both_ff1_ff3", caseBothFf1Ff3());
        emit(out, "all_three", caseAllThree());
        emit(out, "ff1_and_ff2", caseFf1AndFf2());
        emit(out, "ff2_zero_length_meta", caseFf2ZeroLengthMeta());
        emit(out, "ff1_seglen_only_l1", caseFf1SegLenOnlyL1());
        emit(out, "ff3_type1c_flate", caseFf3Type1cFlate());
        emit(out, "ff2_big", caseFf2Big());
        emit(out, "ff1_seglen_nonint", caseFf1SegLenNonInt());
    }

    // ---------------- helpers to build streams ----------------

    private static COSDictionary base() {
        COSDictionary d = new COSDictionary();
        d.setItem(COSName.TYPE, COSName.getPDFName("FontDescriptor"));
        d.setName(COSName.getPDFName("FontName"), "Probe");
        return d;
    }

    private static COSStream rawStream(byte[] data) throws Exception {
        COSStream s = new COSStream();
        try (OutputStream os = s.createOutputStream()) {
            os.write(data);
        }
        return s;
    }

    private static COSStream flateStream(byte[] data) throws Exception {
        COSStream s = new COSStream();
        try (OutputStream os = s.createOutputStream(COSName.FLATE_DECODE)) {
            os.write(data);
        }
        return s;
    }

    private static byte[] repeat(int b, int n) {
        byte[] out = new byte[n];
        for (int i = 0; i < n; i++) {
            out[i] = (byte) b;
        }
        return out;
    }

    // synthetic program payloads — magic bytes + padding to a known length.
    private static byte[] type1Program() {
        // %!PS-AdobeFont clear-text header followed by padding.
        byte[] head = "%!PS-AdobeFont-1.0: Probe\n".getBytes(StandardCharsets.US_ASCII);
        byte[] body = repeat('A', 100 - head.length);
        byte[] all = new byte[100];
        System.arraycopy(head, 0, all, 0, head.length);
        System.arraycopy(body, 0, all, head.length, body.length);
        return all;
    }

    private static byte[] ttfProgram(int size) {
        // 0x00010000 sfnt version + padding.
        byte[] all = repeat('T', size);
        all[0] = 0x00;
        all[1] = 0x01;
        all[2] = 0x00;
        all[3] = 0x00;
        return all;
    }

    private static byte[] ottoProgram() {
        byte[] all = repeat('O', 64);
        all[0] = 'O';
        all[1] = 'T';
        all[2] = 'T';
        all[3] = 'O';
        return all;
    }

    private static byte[] cffProgram() {
        // CFF header: major=1, minor=0, hdrSize=4, offSize=...
        byte[] all = repeat('C', 80);
        all[0] = 0x01;
        all[1] = 0x00;
        all[2] = 0x04;
        all[3] = 0x01;
        return all;
    }

    // ---------------- case dictionaries ----------------

    private static COSDictionary caseNone() {
        return base();
    }

    private static COSDictionary caseFf1Type1Raw() throws Exception {
        COSDictionary d = base();
        d.setItem(COSName.getPDFName("FontFile"), rawStream(type1Program()));
        return d;
    }

    private static COSDictionary caseFf1Type1SegLen() throws Exception {
        COSDictionary d = base();
        COSStream s = rawStream(type1Program());
        s.setInt(COSName.getPDFName("Length1"), 26);
        s.setInt(COSName.getPDFName("Length2"), 60);
        s.setInt(COSName.getPDFName("Length3"), 14);
        d.setItem(COSName.getPDFName("FontFile"), s);
        return d;
    }

    private static COSDictionary caseFf1Type1Flate() throws Exception {
        COSDictionary d = base();
        d.setItem(COSName.getPDFName("FontFile"), flateStream(type1Program()));
        return d;
    }

    private static COSDictionary caseFf1EmptyStream() {
        COSDictionary d = base();
        d.setItem(COSName.getPDFName("FontFile"), new COSStream());
        return d;
    }

    private static COSDictionary caseFf1NonStreamDict() {
        COSDictionary d = base();
        d.setItem(COSName.getPDFName("FontFile"), new COSDictionary());
        return d;
    }

    private static COSDictionary caseFf1NonStreamName() {
        COSDictionary d = base();
        d.setItem(COSName.getPDFName("FontFile"), COSName.getPDFName("oops"));
        return d;
    }

    private static COSDictionary caseFf2TtfRaw() throws Exception {
        COSDictionary d = base();
        d.setItem(COSName.getPDFName("FontFile2"), rawStream(ttfProgram(200)));
        return d;
    }

    private static COSDictionary caseFf2TtfFlate() throws Exception {
        COSDictionary d = base();
        d.setItem(COSName.getPDFName("FontFile2"), flateStream(ttfProgram(200)));
        return d;
    }

    private static COSDictionary caseFf2OttoRaw() throws Exception {
        COSDictionary d = base();
        d.setItem(COSName.getPDFName("FontFile2"), rawStream(ottoProgram()));
        return d;
    }

    private static COSDictionary caseFf2Truncated() throws Exception {
        COSDictionary d = base();
        // Only 2 bytes of the sfnt header — a truncated/corrupt program.
        d.setItem(COSName.getPDFName("FontFile2"), rawStream(new byte[] {0x00, 0x01}));
        return d;
    }

    private static COSDictionary caseFf2NonStream() {
        COSDictionary d = base();
        d.setInt(COSName.getPDFName("FontFile2"), 7);
        return d;
    }

    private static COSDictionary caseFf3Type1c() throws Exception {
        COSDictionary d = base();
        COSStream s = rawStream(cffProgram());
        s.setItem(COSName.SUBTYPE, COSName.getPDFName("Type1C"));
        d.setItem(COSName.getPDFName("FontFile3"), s);
        return d;
    }

    private static COSDictionary caseFf3OpenType() throws Exception {
        COSDictionary d = base();
        COSStream s = rawStream(ottoProgram());
        s.setItem(COSName.SUBTYPE, COSName.getPDFName("OpenType"));
        d.setItem(COSName.getPDFName("FontFile3"), s);
        return d;
    }

    private static COSDictionary caseFf3CidFontType0c() throws Exception {
        COSDictionary d = base();
        COSStream s = rawStream(cffProgram());
        s.setItem(COSName.SUBTYPE, COSName.getPDFName("CIDFontType0C"));
        d.setItem(COSName.getPDFName("FontFile3"), s);
        return d;
    }

    private static COSDictionary caseFf3NoSubtype() throws Exception {
        COSDictionary d = base();
        d.setItem(COSName.getPDFName("FontFile3"), rawStream(cffProgram()));
        return d;
    }

    private static COSDictionary caseFf3SubtypeString() throws Exception {
        COSDictionary d = base();
        COSStream s = rawStream(cffProgram());
        // /Subtype stored as a COSString rather than a COSName.
        s.setItem(COSName.SUBTYPE, new COSString("Type1C"));
        d.setItem(COSName.getPDFName("FontFile3"), s);
        return d;
    }

    private static COSDictionary caseFf3Flate() throws Exception {
        COSDictionary d = base();
        COSStream s = flateStream(cffProgram());
        s.setItem(COSName.SUBTYPE, COSName.getPDFName("Type1C"));
        d.setItem(COSName.getPDFName("FontFile3"), s);
        return d;
    }

    private static COSDictionary caseFf3CorruptShort() throws Exception {
        COSDictionary d = base();
        COSStream s = rawStream(new byte[] {0x01});
        s.setItem(COSName.SUBTYPE, COSName.getPDFName("Type1C"));
        d.setItem(COSName.getPDFName("FontFile3"), s);
        return d;
    }

    private static COSDictionary caseFf3NonStream() {
        COSDictionary d = base();
        d.setItem(COSName.getPDFName("FontFile3"), new COSDictionary());
        return d;
    }

    private static COSDictionary caseBothFf1Ff3() throws Exception {
        COSDictionary d = base();
        d.setItem(COSName.getPDFName("FontFile"), rawStream(type1Program()));
        COSStream s = rawStream(cffProgram());
        s.setItem(COSName.SUBTYPE, COSName.getPDFName("Type1C"));
        d.setItem(COSName.getPDFName("FontFile3"), s);
        return d;
    }

    private static COSDictionary caseAllThree() throws Exception {
        COSDictionary d = base();
        d.setItem(COSName.getPDFName("FontFile"), rawStream(type1Program()));
        d.setItem(COSName.getPDFName("FontFile2"), rawStream(ttfProgram(200)));
        COSStream s = rawStream(cffProgram());
        s.setItem(COSName.SUBTYPE, COSName.getPDFName("OpenType"));
        d.setItem(COSName.getPDFName("FontFile3"), s);
        return d;
    }

    private static COSDictionary caseFf1AndFf2() throws Exception {
        COSDictionary d = base();
        d.setItem(COSName.getPDFName("FontFile"), rawStream(type1Program()));
        d.setItem(COSName.getPDFName("FontFile2"), rawStream(ttfProgram(128)));
        return d;
    }

    private static COSDictionary caseFf2ZeroLengthMeta() throws Exception {
        COSDictionary d = base();
        COSStream s = rawStream(ttfProgram(50));
        // Length1 set to 0 even though body is non-empty (malformed metadata).
        s.setInt(COSName.getPDFName("Length1"), 0);
        d.setItem(COSName.getPDFName("FontFile2"), s);
        return d;
    }

    private static COSDictionary caseFf1SegLenOnlyL1() throws Exception {
        COSDictionary d = base();
        COSStream s = rawStream(type1Program());
        s.setInt(COSName.getPDFName("Length1"), 100);
        d.setItem(COSName.getPDFName("FontFile"), s);
        return d;
    }

    private static COSDictionary caseFf3Type1cFlate() throws Exception {
        COSDictionary d = base();
        COSStream s = flateStream(cffProgram());
        s.setItem(COSName.SUBTYPE, COSName.getPDFName("Type1C"));
        s.setInt(COSName.getPDFName("Length1"), 80);
        d.setItem(COSName.getPDFName("FontFile3"), s);
        return d;
    }

    private static COSDictionary caseFf2Big() throws Exception {
        COSDictionary d = base();
        d.setItem(COSName.getPDFName("FontFile2"), flateStream(ttfProgram(4096)));
        return d;
    }

    private static COSDictionary caseFf1SegLenNonInt() throws Exception {
        COSDictionary d = base();
        COSStream s = rawStream(type1Program());
        // Length1 stored as a COSString — getInt should fall back to default.
        s.setItem(COSName.getPDFName("Length1"), new COSString("26"));
        d.setItem(COSName.getPDFName("FontFile"), s);
        return d;
    }

    // ---------------- projection ----------------

    private static void emit(PrintStream out, String name, COSDictionary dict)
            throws Exception {
        PDFontDescriptor fd = new PDFontDescriptor(dict);
        PDStream ff = fd.getFontFile();
        PDStream ff2 = fd.getFontFile2();
        PDStream ff3 = fd.getFontFile3();

        boolean emb = ff != null || ff2 != null || ff3 != null;

        String len = decodedLen(ff);
        String len2 = decodedLen(ff2);
        String len3 = decodedLen(ff3);

        String sub = "null";
        if (ff3 != null) {
            COSName s = ff3.getCOSObject().getCOSName(COSName.SUBTYPE);
            if (s != null) {
                sub = s.getName();
            }
        }

        int l1 = -1;
        int l2 = -1;
        int l3 = -1;
        if (ff != null) {
            COSDictionary s = ff.getCOSObject();
            l1 = s.getInt(COSName.getPDFName("Length1"), -1);
            l2 = s.getInt(COSName.getPDFName("Length2"), -1);
            l3 = s.getInt(COSName.getPDFName("Length3"), -1);
        }

        StringBuilder sb = new StringBuilder("CASE\t").append(name);
        sb.append("\tff=").append(present(ff));
        sb.append("\tff2=").append(present(ff2));
        sb.append("\tff3=").append(present(ff3));
        sb.append("\temb=").append(emb ? 1 : 0);
        sb.append("\tlen=").append(len);
        sb.append("\tlen2=").append(len2);
        sb.append("\tlen3=").append(len3);
        sb.append("\tsub=").append(sub);
        sb.append("\tl1=").append(l1);
        sb.append("\tl2=").append(l2);
        sb.append("\tl3=").append(l3);
        out.println(sb);
    }

    private static int present(PDStream s) {
        return s == null ? 0 : 1;
    }

    private static String decodedLen(PDStream s) {
        if (s == null) {
            return "-1";
        }
        try {
            return Integer.toString(s.toByteArray().length);
        } catch (Exception e) {
            // PDFBox throws IOException from createInputStream when the stream
            // was never written (empty body). pypdfbox returns b"" (len 0) in
            // that case — pinned as an honest divergence on the Python side.
            return "ERR";
        }
    }
}
