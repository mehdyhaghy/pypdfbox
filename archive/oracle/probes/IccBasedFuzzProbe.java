import java.io.OutputStream;
import java.io.PrintStream;
import java.util.Locale;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSNull;
import org.apache.pdfbox.cos.COSStream;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.pdmodel.common.PDRange;
import org.apache.pdfbox.pdmodel.graphics.color.PDColorSpace;
import org.apache.pdfbox.pdmodel.graphics.color.PDICCBased;

/**
 * Differential fuzz probe for {@code PDICCBased} dictionary / accessor parsing,
 * Apache PDFBox 3.0.7 (wave 1528, agent B).
 *
 * Where the existing {@code ColorSpaceFuzzProbe} drives {@code
 * PDColorSpace.create(COSBase)} construction leniency at a high level, this
 * probe drives the {@code PDICCBased} accessor surface directly: the array form
 * {@code [/ICCBased <stream>]} with malformed {@code /N}, {@code /Alternate},
 * {@code /Range}, {@code /Metadata}. It deliberately embeds NO real ICC profile
 * bytes (or only garbage bytes), so Java's {@code java.awt.color.ICC_Profile}
 * parse fails and {@code iccProfile} stays null — putting Java on the same
 * footing as pypdfbox (which carries no AWT colour space). That isolates the
 * dictionary-parsing / fallback logic from the JVM CMM colour math.
 *
 * Surface exercised per case:
 *   - getNumberOfComponents()   (the /N read; -1 when /N absent)
 *   - getAlternateColorSpace()  (class, or default-by-N, or IOException)
 *   - getRangeForComponent(i)   (min;max per component, default 0..1)
 *   - getMetadata() != null     (the /Metadata stream read)
 *   - getInitialColor()         (components, or ERR)
 *
 * Line grammar (one per case):
 *   CASE &lt;name&gt; ctor=&lt;ERR | ok nc=&lt;n&gt; alt=&lt;class|ERR&gt; \
 *       range=&lt;min:max|...|ERR&gt; meta=&lt;0|1&gt; init=&lt;a,b,..|ERR&gt;&gt;
 *
 * "ctor=ERR" means the PDICCBased(array) constructor threw. "alt=ERR" means
 * getAlternateColorSpace() threw (Java throws IOException when /N is not in
 * {1,3,4} and /Alternate is absent). "range" is getRangeForComponent(i) for
 * i in [0, nc) joined by '|' (each "min:max" with %.3f), or ERR / EMPTY when
 * nc&lt;=0. "meta" is 1 when getMetadata() returns non-null.
 */
public final class IccBasedFuzzProbe {

    static PrintStream out;

    static COSName n(String s) {
        return COSName.getPDFName(s);
    }

    static COSArray arr(COSBase... items) {
        COSArray a = new COSArray();
        for (COSBase b : items) {
            a.add(b);
        }
        return a;
    }

    static COSArray floats(double... vals) {
        COSArray a = new COSArray();
        for (double v : vals) {
            a.add(new COSFloat((float) v));
        }
        return a;
    }

    // An /ICCBased stream: optional /N (omitted when nVal == Integer.MIN_VALUE),
    // optional profile body, optional /Alternate, /Range, /Metadata.
    static COSStream icc(Integer nVal, byte[] body, COSBase alt, COSArray range,
            COSStream meta) throws Exception {
        COSStream s = new COSStream();
        if (nVal != null) {
            s.setInt(COSName.N, nVal);
        }
        if (alt != null) {
            s.setItem(COSName.ALTERNATE, alt);
        }
        if (range != null) {
            s.setItem(COSName.RANGE, range);
        }
        if (meta != null) {
            s.setItem(COSName.METADATA, meta);
        }
        OutputStream os = s.createOutputStream();
        if (body != null) {
            os.write(body);
        }
        os.close();
        return s;
    }

    static COSStream metaStream() throws Exception {
        COSStream s = new COSStream();
        s.setItem(COSName.TYPE, COSName.METADATA);
        s.setItem(COSName.SUBTYPE, n("XML"));
        OutputStream os = s.createOutputStream();
        os.write("<x:xmpmeta/>".getBytes("US-ASCII"));
        os.close();
        return s;
    }

    static void emit(String name, COSArray array) {
        StringBuilder sb = new StringBuilder("CASE ").append(name).append(' ');
        PDICCBased cs;
        try {
            PDColorSpace created = PDColorSpace.create(array, null);
            if (!(created instanceof PDICCBased)) {
                out.println(sb.append("ctor=NOTICC class=").append(
                        created == null ? "NULL"
                                : created.getClass().getSimpleName()).toString());
                return;
            }
            cs = (PDICCBased) created;
        } catch (Throwable t) {
            out.println(sb.append("ctor=ERR").toString());
            return;
        }
        sb.append("ctor=ok");
        int nc;
        try {
            nc = cs.getNumberOfComponents();
            sb.append(" nc=").append(nc);
        } catch (Throwable t) {
            out.println(sb.append(" nc=ERR").toString());
            return;
        }
        // getAlternateColorSpace(): class name, or ERR if it throws.
        try {
            PDColorSpace alt = cs.getAlternateColorSpace();
            sb.append(" alt=").append(
                    alt == null ? "NULL" : alt.getClass().getSimpleName());
        } catch (Throwable t) {
            sb.append(" alt=ERR");
        }
        // getRangeForComponent(i) for each component.
        if (nc <= 0) {
            sb.append(" range=EMPTY");
        } else {
            try {
                StringBuilder rb = new StringBuilder();
                for (int i = 0; i < nc; i++) {
                    if (i > 0) {
                        rb.append('|');
                    }
                    PDRange r = cs.getRangeForComponent(i);
                    rb.append(String.format(Locale.ROOT, "%.3f:%.3f",
                            r.getMin(), r.getMax()));
                }
                sb.append(" range=").append(rb);
            } catch (Throwable t) {
                sb.append(" range=ERR");
            }
        }
        // getMetadata() presence.
        try {
            sb.append(" meta=").append(cs.getMetadata() != null ? 1 : 0);
        } catch (Throwable t) {
            sb.append(" meta=ERR");
        }
        // getInitialColor() components.
        try {
            float[] init = cs.getInitialColor().getComponents();
            sb.append(" init=");
            for (int i = 0; i < init.length; i++) {
                if (i > 0) {
                    sb.append(',');
                }
                sb.append(String.format(Locale.ROOT, "%.3f", init[i]));
            }
        } catch (Throwable t) {
            sb.append(" init=ERR");
        }
        out.println(sb.toString());
    }

    public static void main(String[] args) throws Exception {
        out = new PrintStream(System.out, true, "UTF-8");

        byte[] garbage = "this is not an icc profile".getBytes("US-ASCII");
        byte[] shortBytes = new byte[] {0, 1, 2, 3};

        // ===== /N variations (no embedded profile -> iccProfile null) =====
        emit("n1", arr(n("ICCBased"), icc(1, null, null, null, null)));
        emit("n3", arr(n("ICCBased"), icc(3, null, null, null, null)));
        emit("n4", arr(n("ICCBased"), icc(4, null, null, null, null)));
        emit("n0", arr(n("ICCBased"), icc(0, null, null, null, null)));
        emit("n2", arr(n("ICCBased"), icc(2, null, null, null, null)));
        emit("n5", arr(n("ICCBased"), icc(5, null, null, null, null)));
        emit("n_negative", arr(n("ICCBased"), icc(-3, null, null, null, null)));
        // /N absent entirely.
        emit("n_absent", arr(n("ICCBased"), icc(null, null, null, null, null)));

        // ===== /N with garbage / short profile body (still null profile) =====
        emit("n3_garbage", arr(n("ICCBased"), icc(3, garbage, null, null, null)));
        emit("n4_garbage", arr(n("ICCBased"), icc(4, garbage, null, null, null)));
        emit("n3_short", arr(n("ICCBased"), icc(3, shortBytes, null, null, null)));

        // ===== /Alternate present (name + array forms) =====
        emit("alt_devicegray",
                arr(n("ICCBased"), icc(1, null, COSName.DEVICEGRAY, null, null)));
        emit("alt_devicergb",
                arr(n("ICCBased"), icc(3, null, COSName.DEVICERGB, null, null)));
        emit("alt_devicecmyk",
                arr(n("ICCBased"), icc(4, null, COSName.DEVICECMYK, null, null)));
        // /Alternate disagrees with /N (N=3 but alternate is gray).
        emit("alt_mismatch_n3_gray",
                arr(n("ICCBased"), icc(3, null, COSName.DEVICEGRAY, null, null)));
        // /Alternate as a one-element array.
        emit("alt_array_rgb",
                arr(n("ICCBased"), icc(3, null, arr(COSName.DEVICERGB), null, null)));
        // /Alternate unknown name.
        emit("alt_unknown_name",
                arr(n("ICCBased"), icc(3, null, n("FooBar"), null, null)));
        // /Alternate present but N invalid (2): alt is explicit so no throw.
        emit("alt_present_n2",
                arr(n("ICCBased"), icc(2, null, COSName.DEVICERGB, null, null)));
        // /Alternate is wrong type (integer): Java throws "expected COSArray or
        // COSName".
        emit("alt_wrong_type",
                arr(n("ICCBased"), icc(3, null, COSInteger.get(7), null, null)));

        // ===== default-alternate-by-N (no /Alternate) =====
        // N=1/3/4 -> DeviceGray/RGB/CMYK; N=0/2/5 -> Java throws IOException.
        emit("default_alt_n1", arr(n("ICCBased"), icc(1, null, null, null, null)));
        emit("default_alt_n3", arr(n("ICCBased"), icc(3, null, null, null, null)));
        emit("default_alt_n4", arr(n("ICCBased"), icc(4, null, null, null, null)));

        // ===== /Range corners =====
        emit("range_ok_n3",
                arr(n("ICCBased"),
                        icc(3, null, COSName.DEVICERGB,
                                floats(0, 1, 0, 1, 0, 1), null)));
        emit("range_custom_n3",
                arr(n("ICCBased"),
                        icc(3, null, COSName.DEVICERGB,
                                floats(-1, 2, -1, 2, -1, 2), null)));
        // /Range too short -> default 0..1 for all components.
        emit("range_short_n3",
                arr(n("ICCBased"),
                        icc(3, null, COSName.DEVICERGB, floats(0, 1), null)));
        // /Range empty -> default.
        emit("range_empty_n3",
                arr(n("ICCBased"),
                        icc(3, null, COSName.DEVICERGB, new COSArray(), null)));
        // /Range non-numeric entries.
        COSArray badRange = new COSArray();
        badRange.add(n("x"));
        badRange.add(n("y"));
        badRange.add(n("x"));
        badRange.add(n("y"));
        badRange.add(n("x"));
        badRange.add(n("y"));
        emit("range_nonnumeric_n3",
                arr(n("ICCBased"),
                        icc(3, null, COSName.DEVICERGB, badRange, null)));
        // /Range with extra entries (longer than 2*N).
        emit("range_long_n1",
                arr(n("ICCBased"),
                        icc(1, null, COSName.DEVICEGRAY,
                                floats(0, 1, 5, 9), null)));

        // ===== /Metadata corners =====
        emit("meta_present",
                arr(n("ICCBased"),
                        icc(3, null, COSName.DEVICERGB, null, metaStream())));
        emit("meta_absent",
                arr(n("ICCBased"),
                        icc(3, null, COSName.DEVICERGB, null, null)));

        // ===== empty / malformed stream body =====
        emit("empty_body_n3", arr(n("ICCBased"), icc(3, new byte[0], null, null, null)));
        emit("body_with_null_n1",
                arr(n("ICCBased"),
                        icc(1, new byte[] {0, 0, 0, 0}, null, null, null)));

        // ===== combined garbage profile + alternate fallback =====
        emit("garbage_with_alt_cmyk",
                arr(n("ICCBased"),
                        icc(4, garbage, COSName.DEVICECMYK, null, null)));
        emit("garbage_default_alt_n4",
                arr(n("ICCBased"), icc(4, garbage, null, null, null)));

        // ===== second element not a stream =====
        // PDICCBased(array) expects a stream in slot 1; a name should make the
        // constructor (or accessor) misbehave consistently.
        emit("second_not_stream", arr(n("ICCBased"), COSName.DEVICERGB));
        // Only one element.
        emit("one_element", arr(n("ICCBased")));
        // Second element COSNull.
        emit("second_cosnull", arr(n("ICCBased"), COSNull.NULL));
        // Second element a string.
        emit("second_string", arr(n("ICCBased"), new COSString("x")));
    }
}
