import java.io.ByteArrayInputStream;
import java.io.PrintStream;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSStream;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.common.PDStream;
import org.apache.pdfbox.pdmodel.graphics.color.PDColorSpace;
import org.apache.pdfbox.pdmodel.graphics.image.PDImageXObject;

/**
 * In-memory construction-contract fuzz probe for {@code PDImageXObject}
 * metadata accessors, Apache PDFBox 3.0.7 (wave 1546, agent B).
 *
 * <p>Complements the file-driven {@code ImageXObjectFuzzProbe} (wave 1513),
 * which loads malformed PDFs off disk and projects a coarse one-line summary
 * ({@code w/h/bpc/cs/mask/im/interp/decode/filt/suffix}). This probe instead
 * builds each {@code PDImageXObject} <i>programmatically</i> over a fuzzed
 * {@code COSStream} (no file round-trip, no xref/parser involvement) and
 * projects the FINER accessor surface the wave-1513 probe did not exercise:
 * <ul>
 *   <li>{@code getColorKeyMask()} as the decoded {@code COSArray} int list —
 *       not just the {@code key}/{@code stream}/{@code other} bucket;</li>
 *   <li>{@code getDecode()} as the raw {@code COSArray} contents (incl. the
 *       wrong-arity and non-numeric-element cases);</li>
 *   <li>{@code getMask()} class-name + {@code getColorKeyMask()} mutual
 *       exclusion (stream vs array vs name vs dict);</li>
 *   <li>{@code getSoftMask()} presence + {@code throws} contract over a
 *       non-stream {@code /SMask};</li>
 *   <li>{@code getStructParent()} default and value;</li>
 *   <li>{@code getSuffix()} across the full filter matrix incl. JBIG2;</li>
 *   <li>{@code getBitsPerComponent()} stencil-forcing to 1 regardless of the
 *       dictionary entry; {@code /ImageMask true} with bpc != 1.</li>
 * </ul>
 *
 * <p>Output grammar — one line per case, in the fixed order emitted by
 * {@link #main}:
 * <pre>
 *   CASE &lt;name&gt; w=&lt;int&gt; h=&lt;int&gt; bpc=&lt;int&gt; im=&lt;0|1&gt; \
 *        cs=&lt;tok&gt; decode=&lt;tok&gt; ckey=&lt;tok&gt; mask=&lt;tok&gt; \
 *        smask=&lt;tok&gt; sp=&lt;int&gt; suffix=&lt;tok&gt;
 * </pre>
 * Tokens: {@code cs} = colour-space name / {@code NONE} / {@code ERR};
 * {@code decode} = comma-joined {@code getDecode()} numbers / {@code none};
 * {@code ckey} = comma-joined {@code getColorKeyMask()} ints / {@code none};
 * {@code mask} = {@code getMask()} simple class name / {@code none} /
 * {@code ERR}; {@code smask} = same for {@code getSoftMask()}; {@code suffix}
 * = {@code getSuffix()} or {@code null}.
 */
public final class ImageXObjectMetaFuzzProbe {

    static PrintStream out;
    static PDDocument doc;

    static String num(COSBase v) {
        if (v instanceof COSInteger) {
            return Long.toString(((COSInteger) v).longValue());
        }
        if (v instanceof COSFloat) {
            return v.toString();
        }
        return "?";
    }

    static COSStream newImageStream(byte[] data) throws Exception {
        PDStream pds = new PDStream(doc, new ByteArrayInputStream(data));
        COSStream cos = pds.getCOSObject();
        cos.setItem(COSName.TYPE, COSName.XOBJECT);
        cos.setItem(COSName.SUBTYPE, COSName.IMAGE);
        return cos;
    }

    static COSArray ints(long... xs) {
        COSArray a = new COSArray();
        for (long x : xs) {
            a.add(COSInteger.get(x));
        }
        return a;
    }

    static COSArray floats(double... xs) {
        COSArray a = new COSArray();
        for (double x : xs) {
            a.add(new COSFloat((float) x));
        }
        return a;
    }

    static String arrToken(COSArray a) {
        if (a == null) {
            return "none";
        }
        if (a.size() == 0) {
            return "[]";
        }
        StringBuilder s = new StringBuilder();
        for (int i = 0; i < a.size(); i++) {
            if (i > 0) {
                s.append(',');
            }
            s.append(num(a.get(i)));
        }
        return s.toString();
    }

    static String intArrToken(COSArray a) {
        // getColorKeyMask() returns the raw COSArray; mirror the int[] decode
        // pypdfbox exposes (getColorKeyMask -> list[int]).
        if (a == null) {
            return "none";
        }
        if (a.size() == 0) {
            return "[]";
        }
        StringBuilder s = new StringBuilder();
        for (int i = 0; i < a.size(); i++) {
            if (i > 0) {
                s.append(',');
            }
            COSBase b = a.get(i);
            if (b instanceof COSInteger) {
                s.append(((COSInteger) b).intValue());
            } else if (b instanceof COSFloat) {
                s.append((int) ((COSFloat) b).floatValue());
            } else {
                s.append('?');
            }
        }
        return s.toString();
    }

    static String csToken(PDImageXObject img) {
        try {
            PDColorSpace cs = img.getColorSpace();
            return cs == null ? "NONE" : cs.getName();
        } catch (Throwable t) {
            return "ERR";
        }
    }

    static String maskToken(PDImageXObject img) {
        try {
            PDImageXObject m = img.getMask();
            return m == null ? "none" : "stream";
        } catch (Throwable t) {
            return "ERR";
        }
    }

    static String smaskToken(PDImageXObject img) {
        try {
            PDImageXObject m = img.getSoftMask();
            return m == null ? "none" : "stream";
        } catch (Throwable t) {
            return "ERR";
        }
    }

    static void project(String name, PDImageXObject img) {
        StringBuilder sb = new StringBuilder();
        sb.append("CASE ").append(name);
        sb.append(" w=").append(img.getWidth());
        sb.append(" h=").append(img.getHeight());
        sb.append(" bpc=").append(img.getBitsPerComponent());
        sb.append(" im=").append(img.isStencil() ? "1" : "0");
        sb.append(" cs=").append(csToken(img));
        sb.append(" decode=").append(arrToken(img.getDecode()));
        sb.append(" ckey=").append(intArrToken(img.getColorKeyMask()));
        sb.append(" mask=").append(maskToken(img));
        sb.append(" smask=").append(smaskToken(img));
        sb.append(" sp=").append(img.getStructParent());
        String suffix;
        try {
            suffix = img.getSuffix();
        } catch (Throwable t) {
            suffix = "ERR";
        }
        sb.append(" suffix=").append(suffix == null ? "null" : suffix);
        out.println(sb.toString());
    }

    static void emit(String name, COSStream cos) {
        try {
            PDImageXObject img = new PDImageXObject(new PDStream(cos), null);
            project(name, img);
        } catch (Throwable t) {
            out.println("CASE " + name + " ERR:" + t.getClass().getSimpleName());
        }
    }

    public static void main(String[] args) throws Exception {
        out = new PrintStream(System.out, true, "UTF-8");
        doc = new PDDocument();

        byte[] data = new byte[64];

        // ---- /Width /Height fuzz ----
        COSStream c;

        c = newImageStream(data);
        emit("wh_missing", c);

        c = newImageStream(data);
        c.setInt(COSName.WIDTH, 0);
        c.setInt(COSName.HEIGHT, 0);
        emit("wh_zero", c);

        c = newImageStream(data);
        c.setInt(COSName.WIDTH, -4);
        c.setInt(COSName.HEIGHT, -4);
        emit("wh_negative", c);

        c = newImageStream(data);
        c.setItem(COSName.WIDTH, new COSFloat(4.5f));
        c.setItem(COSName.HEIGHT, new COSFloat(4.5f));
        emit("wh_float", c);

        c = newImageStream(data);
        c.setItem(COSName.WIDTH, COSName.getPDFName("x"));
        emit("w_name", c);

        // ---- /BitsPerComponent fuzz ----
        c = newImageStream(data);
        c.setInt(COSName.WIDTH, 4);
        c.setInt(COSName.HEIGHT, 4);
        c.setInt(COSName.BITS_PER_COMPONENT, 16);
        c.setItem(COSName.COLORSPACE, COSName.DEVICEGRAY);
        emit("bpc_16", c);

        c = newImageStream(data);
        c.setInt(COSName.WIDTH, 4);
        c.setInt(COSName.HEIGHT, 4);
        c.setInt(COSName.BITS_PER_COMPONENT, 3);
        c.setItem(COSName.COLORSPACE, COSName.DEVICEGRAY);
        emit("bpc_3", c);

        c = newImageStream(data);
        c.setInt(COSName.WIDTH, 4);
        c.setInt(COSName.HEIGHT, 4);
        c.setInt(COSName.BITS_PER_COMPONENT, 0);
        c.setItem(COSName.COLORSPACE, COSName.DEVICEGRAY);
        emit("bpc_0", c);

        c = newImageStream(data);
        c.setInt(COSName.WIDTH, 4);
        c.setInt(COSName.HEIGHT, 4);
        // /BPC short alias only.
        c.setInt(COSName.getPDFName("BPC"), 8);
        c.setItem(COSName.COLORSPACE, COSName.DEVICEGRAY);
        emit("bpc_short_alias", c);

        // ---- /ImageMask stencil forcing ----
        c = newImageStream(data);
        c.setInt(COSName.WIDTH, 4);
        c.setInt(COSName.HEIGHT, 4);
        c.setBoolean(COSName.IMAGE_MASK, true);
        emit("imagemask_true_no_bpc", c);

        c = newImageStream(data);
        c.setInt(COSName.WIDTH, 4);
        c.setInt(COSName.HEIGHT, 4);
        c.setBoolean(COSName.IMAGE_MASK, true);
        c.setInt(COSName.BITS_PER_COMPONENT, 8);
        emit("imagemask_true_bpc8", c);

        c = newImageStream(data);
        c.setInt(COSName.WIDTH, 4);
        c.setInt(COSName.HEIGHT, 4);
        c.setBoolean(COSName.IMAGE_MASK, false);
        c.setInt(COSName.BITS_PER_COMPONENT, 1);
        emit("imagemask_false", c);

        // ---- /ColorSpace fuzz ----
        c = newImageStream(data);
        c.setInt(COSName.WIDTH, 4);
        c.setInt(COSName.HEIGHT, 4);
        c.setInt(COSName.BITS_PER_COMPONENT, 8);
        c.setItem(COSName.COLORSPACE, COSName.DEVICERGB);
        emit("cs_devicergb", c);

        c = newImageStream(data);
        c.setInt(COSName.WIDTH, 4);
        c.setInt(COSName.HEIGHT, 4);
        c.setInt(COSName.BITS_PER_COMPONENT, 8);
        c.setItem(COSName.COLORSPACE, COSName.getPDFName("Bogus"));
        emit("cs_unknown_name", c);

        c = newImageStream(data);
        c.setInt(COSName.WIDTH, 4);
        c.setInt(COSName.HEIGHT, 4);
        c.setInt(COSName.BITS_PER_COMPONENT, 8);
        emit("cs_missing", c);

        c = newImageStream(data);
        c.setInt(COSName.WIDTH, 4);
        c.setInt(COSName.HEIGHT, 4);
        c.setBoolean(COSName.IMAGE_MASK, true);
        emit("cs_missing_stencil", c);

        // ---- /Decode fuzz ----
        c = newImageStream(data);
        c.setInt(COSName.WIDTH, 4);
        c.setInt(COSName.HEIGHT, 4);
        c.setInt(COSName.BITS_PER_COMPONENT, 8);
        c.setItem(COSName.COLORSPACE, COSName.DEVICEGRAY);
        c.setItem(COSName.DECODE, floats(0.0, 1.0));
        emit("decode_normal", c);

        c = newImageStream(data);
        c.setInt(COSName.WIDTH, 4);
        c.setInt(COSName.HEIGHT, 4);
        c.setInt(COSName.BITS_PER_COMPONENT, 8);
        c.setItem(COSName.COLORSPACE, COSName.DEVICEGRAY);
        c.setItem(COSName.DECODE, floats(1.0, 0.0));
        emit("decode_reversed", c);

        c = newImageStream(data);
        c.setInt(COSName.WIDTH, 4);
        c.setInt(COSName.HEIGHT, 4);
        c.setInt(COSName.BITS_PER_COMPONENT, 8);
        c.setItem(COSName.COLORSPACE, COSName.DEVICERGB);
        c.setItem(COSName.DECODE, floats(0.0, 1.0));
        emit("decode_wrong_arity", c);

        c = newImageStream(data);
        c.setInt(COSName.WIDTH, 4);
        c.setInt(COSName.HEIGHT, 4);
        c.setInt(COSName.BITS_PER_COMPONENT, 8);
        c.setItem(COSName.COLORSPACE, COSName.DEVICEGRAY);
        c.setItem(COSName.DECODE, new COSArray());
        emit("decode_empty", c);

        c = newImageStream(data);
        c.setInt(COSName.WIDTH, 4);
        c.setInt(COSName.HEIGHT, 4);
        c.setInt(COSName.BITS_PER_COMPONENT, 8);
        c.setItem(COSName.COLORSPACE, COSName.DEVICEGRAY);
        COSArray mixed = new COSArray();
        mixed.add(COSInteger.get(0));
        mixed.add(COSName.getPDFName("oops"));
        c.setItem(COSName.DECODE, mixed);
        emit("decode_nonnumeric", c);

        c = newImageStream(data);
        c.setInt(COSName.WIDTH, 4);
        c.setInt(COSName.HEIGHT, 4);
        c.setInt(COSName.BITS_PER_COMPONENT, 8);
        c.setItem(COSName.COLORSPACE, COSName.DEVICEGRAY);
        c.setItem(COSName.DECODE, COSName.getPDFName("notarray"));
        emit("decode_not_array", c);

        // ---- /Mask fuzz (color-key array vs stream vs name vs dict) ----
        c = newImageStream(data);
        c.setInt(COSName.WIDTH, 4);
        c.setInt(COSName.HEIGHT, 4);
        c.setInt(COSName.BITS_PER_COMPONENT, 8);
        c.setItem(COSName.COLORSPACE, COSName.DEVICEGRAY);
        c.setItem(COSName.MASK, ints(0, 5));
        emit("mask_colorkey", c);

        c = newImageStream(data);
        c.setInt(COSName.WIDTH, 4);
        c.setInt(COSName.HEIGHT, 4);
        c.setInt(COSName.BITS_PER_COMPONENT, 8);
        c.setItem(COSName.COLORSPACE, COSName.DEVICEGRAY);
        c.setItem(COSName.MASK, ints(0, 5, 0, 5, 0, 5));
        emit("mask_colorkey_rgb", c);

        c = newImageStream(data);
        c.setInt(COSName.WIDTH, 4);
        c.setInt(COSName.HEIGHT, 4);
        c.setInt(COSName.BITS_PER_COMPONENT, 8);
        c.setItem(COSName.COLORSPACE, COSName.DEVICEGRAY);
        c.setItem(COSName.MASK, floats(0.0, 5.0));
        emit("mask_colorkey_float", c);

        c = newImageStream(data);
        c.setInt(COSName.WIDTH, 4);
        c.setInt(COSName.HEIGHT, 4);
        c.setInt(COSName.BITS_PER_COMPONENT, 8);
        c.setItem(COSName.COLORSPACE, COSName.DEVICEGRAY);
        c.setItem(COSName.MASK, newImageStream(new byte[]{0}));
        emit("mask_stream", c);

        c = newImageStream(data);
        c.setInt(COSName.WIDTH, 4);
        c.setInt(COSName.HEIGHT, 4);
        c.setInt(COSName.BITS_PER_COMPONENT, 8);
        c.setItem(COSName.COLORSPACE, COSName.DEVICEGRAY);
        c.setItem(COSName.MASK, COSName.getPDFName("garbage"));
        emit("mask_name", c);

        // ---- /SMask fuzz ----
        c = newImageStream(data);
        c.setInt(COSName.WIDTH, 4);
        c.setInt(COSName.HEIGHT, 4);
        c.setInt(COSName.BITS_PER_COMPONENT, 8);
        c.setItem(COSName.COLORSPACE, COSName.DEVICEGRAY);
        c.setItem(COSName.SMASK, newImageStream(new byte[]{0}));
        emit("smask_stream", c);

        c = newImageStream(data);
        c.setInt(COSName.WIDTH, 4);
        c.setInt(COSName.HEIGHT, 4);
        c.setInt(COSName.BITS_PER_COMPONENT, 8);
        c.setItem(COSName.COLORSPACE, COSName.DEVICEGRAY);
        c.setItem(COSName.SMASK, ints(0, 5));
        emit("smask_array", c);

        c = newImageStream(data);
        c.setInt(COSName.WIDTH, 4);
        c.setInt(COSName.HEIGHT, 4);
        c.setInt(COSName.BITS_PER_COMPONENT, 8);
        c.setItem(COSName.COLORSPACE, COSName.DEVICEGRAY);
        c.setItem(COSName.SMASK, COSName.getPDFName("nope"));
        emit("smask_name", c);

        // ---- /Interpolate fuzz ----
        c = newImageStream(data);
        c.setInt(COSName.WIDTH, 4);
        c.setInt(COSName.HEIGHT, 4);
        c.setInt(COSName.BITS_PER_COMPONENT, 8);
        c.setItem(COSName.COLORSPACE, COSName.DEVICEGRAY);
        c.setItem(COSName.INTERPOLATE, COSInteger.get(1));
        emit("interp_int", c);

        // ---- /StructParent ----
        c = newImageStream(data);
        c.setInt(COSName.WIDTH, 4);
        c.setInt(COSName.HEIGHT, 4);
        c.setInt(COSName.BITS_PER_COMPONENT, 8);
        c.setItem(COSName.COLORSPACE, COSName.DEVICEGRAY);
        c.setInt(COSName.STRUCT_PARENT, 7);
        emit("structparent_7", c);

        // ---- /Suffix across filter matrix ----
        emitSuffix("suffix_no_filter", null);
        emitSuffix("suffix_flate", COSName.FLATE_DECODE);
        emitSuffix("suffix_lzw", COSName.LZW_DECODE);
        emitSuffix("suffix_runlength", COSName.RUN_LENGTH_DECODE);
        emitSuffix("suffix_dct", COSName.DCT_DECODE);
        emitSuffix("suffix_jpx", COSName.JPX_DECODE);
        emitSuffix("suffix_ccitt", COSName.CCITTFAX_DECODE);
        emitSuffix("suffix_jbig2", COSName.JBIG2_DECODE);
        emitSuffix("suffix_ascii85", COSName.ASCII85_DECODE);

        doc.close();
    }

    static void emitSuffix(String name, COSName filter) {
        try {
            // No real payload — getSuffix() reads only the /Filter list.
            COSStream cos = doc.getDocument().createCOSStream();
            cos.setItem(COSName.TYPE, COSName.XOBJECT);
            cos.setItem(COSName.SUBTYPE, COSName.IMAGE);
            cos.setInt(COSName.WIDTH, 4);
            cos.setInt(COSName.HEIGHT, 4);
            cos.setInt(COSName.BITS_PER_COMPONENT, 8);
            cos.setItem(COSName.COLORSPACE, COSName.DEVICEGRAY);
            if (filter != null) {
                cos.setItem(COSName.FILTER, filter);
            }
            PDImageXObject img = new PDImageXObject(new PDStream(cos), null);
            String suffix = img.getSuffix();
            out.println("CASE " + name + " suffix=" + (suffix == null ? "null" : suffix));
        } catch (Throwable t) {
            out.println("CASE " + name + " ERR:" + t.getClass().getSimpleName());
        }
    }
}
