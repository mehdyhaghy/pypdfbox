import java.io.PrintStream;
import java.util.List;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSBoolean;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSNull;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.pdmodel.PDResources;
import org.apache.pdfbox.pdmodel.graphics.color.PDColorSpace;
import org.apache.pdfbox.pdmodel.graphics.image.PDInlineImage;

/**
 * Live oracle probe (wave 1541): differential-fuzz the {@code PDInlineImage}
 * OBJECT API surface — the getter projection of an inline-image parameter
 * dictionary, isolated from the BI/ID/EI tokenizer.
 *
 * <p>Complements the existing inline probes which work at the parser level
 * ({@code InlineImageFuzzProbe}, {@code InlineImageDictProbe},
 * {@code InlineEiScanProbe}) or pin a narrow facet
 * ({@code InlineImageKeyResolveProbe} = key precedence,
 * {@code InlineCsResolveProbe} = colour-space class). This probe constructs a
 * {@code PDInlineImage} directly over 44 malformed/edge-case parameter dicts
 * and projects, per case, a COMBINED tuple of every scalar getter plus the
 * colour-space identity, filter list, decode array and suffix — so a
 * divergence in ANY of those facets, or a construction throw, is caught.
 *
 * <p>Cases cover: abbreviated vs full keys (W/Width, H/Height,
 * BPC/BitsPerComponent, CS/ColorSpace, F/Filter, IM/ImageMask, D/Decode);
 * {@code /CS} abbreviations (G/RGB/CMYK/I), named resource colour space and
 * unknown name; {@code /F} abbreviations (AHx/A85/LZW/Fl/RL) single and array,
 * plus an unknown filter; {@code /BPC} missing/0/negative/non-int; {@code /W}
 * {@code /H} missing/zero/negative/non-int/float; {@code /IM true} with a
 * mismatched {@code /BPC}; and {@code /Decode} of wrong arity.
 *
 * <p>Construction itself decodes the filter chain eagerly, so an unknown
 * filter throws out of the constructor — those cases emit {@code THROW}
 * (exception class names differ across the port, so only the throw-vs-not
 * fact is compared). Empty raw data ({@code new byte[0]}) keeps decode of the
 * real filters (AHx/A85/Fl/RL/LZW) cheap and lossless.
 *
 * <p>Output (UTF-8): one {@code label|...} line per case. Per-getter throws
 * are rendered inline as {@code <throw>} so divergence in the throw boundary
 * is also pinned.
 *
 * <p>Usage: {@code java -cp <pdfbox-app.jar>:<build> InlineImageApiFuzzProbe}
 */
public final class InlineImageApiFuzzProbe {

    static COSName n(String s) {
        return COSName.getPDFName(s);
    }

    static PDInlineImage img(COSDictionary d, PDResources res) throws Exception {
        return new PDInlineImage(d, new byte[0], res);
    }

    /** Project the full getter tuple for an already-constructed image. */
    static String project(PDInlineImage im) {
        StringBuilder s = new StringBuilder();
        s.append("w=").append(safeInt(() -> im.getWidth()));
        s.append(" h=").append(safeInt(() -> im.getHeight()));
        s.append(" bpc=").append(safeInt(() -> im.getBitsPerComponent()));
        s.append(" stencil=").append(safeBool(() -> im.isStencil()));
        s.append(" interp=").append(safeBool(() -> im.getInterpolate()));
        s.append(" cs=").append(safeCsName(im));
        s.append(" csclass=").append(safeCsClass(im));
        s.append(" filters=").append(filters(im));
        s.append(" decode=").append(decode(im));
        s.append(" suffix=").append(safeStr(() -> im.getSuffix()));
        return s.toString();
    }

    interface IntThunk {
        int get();
    }

    interface BoolThunk {
        boolean get();
    }

    interface StrThunk {
        String get();
    }

    static String safeInt(IntThunk t) {
        try {
            return Integer.toString(t.get());
        } catch (Throwable e) {
            return "<throw>";
        }
    }

    static String safeBool(BoolThunk t) {
        try {
            return t.get() ? "true" : "false";
        } catch (Throwable e) {
            return "<throw>";
        }
    }

    static String safeStr(StrThunk t) {
        try {
            return t.get();
        } catch (Throwable e) {
            return "<throw>";
        }
    }

    static String safeCsName(PDInlineImage im) {
        try {
            PDColorSpace cs = im.getColorSpace();
            return cs == null ? "null" : cs.getName();
        } catch (Throwable e) {
            return "<throw>";
        }
    }

    static String safeCsClass(PDInlineImage im) {
        try {
            PDColorSpace cs = im.getColorSpace();
            return cs == null ? "null" : cs.getClass().getSimpleName();
        } catch (Throwable e) {
            return "<throw>";
        }
    }

    static String filters(PDInlineImage im) {
        try {
            List<String> f = im.getFilters();
            if (f == null) {
                return "null";
            }
            StringBuilder s = new StringBuilder("[");
            for (int i = 0; i < f.size(); i++) {
                if (i > 0) {
                    s.append(',');
                }
                s.append(f.get(i));
            }
            return s.append(']').toString();
        } catch (Throwable e) {
            return "<throw>";
        }
    }

    static String decode(PDInlineImage im) {
        try {
            COSArray d = im.getDecode();
            if (d == null) {
                return "null";
            }
            StringBuilder s = new StringBuilder("[");
            for (int i = 0; i < d.size(); i++) {
                if (i > 0) {
                    s.append(',');
                }
                COSBase v = d.get(i);
                if (v instanceof COSInteger) {
                    s.append(((COSInteger) v).longValue());
                } else if (v instanceof COSFloat) {
                    s.append(((COSFloat) v).floatValue());
                } else {
                    s.append(v == null ? "null" : v.getClass().getSimpleName());
                }
            }
            return s.append(']').toString();
        } catch (Throwable e) {
            return "<throw>";
        }
    }

    /** Construct + project, capturing a construction throw as a whole-line THROW. */
    static String run(String label, COSDictionary d, PDResources res) {
        try {
            return label + "|" + project(img(d, res));
        } catch (Throwable t) {
            return label + "|THROW";
        }
    }

    static PDResources resourcesWithRgbAlias() {
        PDResources res = new PDResources();
        COSDictionary csDict = new COSDictionary();
        csDict.setItem(n("CS0"), n("DeviceRGB"));
        res.getCOSObject().setItem(COSName.COLORSPACE, csDict);
        return res;
    }

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        StringBuilder sb = new StringBuilder();

        // --- abbreviated vs full keys ---
        COSDictionary d;

        d = new COSDictionary();
        d.setItem(n("W"), COSInteger.get(4));
        d.setItem(n("H"), COSInteger.get(3));
        d.setItem(n("BPC"), COSInteger.get(8));
        d.setItem(n("CS"), n("G"));
        sb.append(run("abbrev_gray", d, null)).append('\n');

        d = new COSDictionary();
        d.setItem(n("Width"), COSInteger.get(4));
        d.setItem(n("Height"), COSInteger.get(3));
        d.setItem(n("BitsPerComponent"), COSInteger.get(8));
        d.setItem(n("ColorSpace"), n("DeviceGray"));
        sb.append(run("full_gray", d, null)).append('\n');

        // short wins over long
        d = new COSDictionary();
        d.setItem(n("W"), COSInteger.get(5));
        d.setItem(n("Width"), COSInteger.get(50));
        d.setItem(n("H"), COSInteger.get(6));
        d.setItem(n("Height"), COSInteger.get(60));
        sb.append(run("short_wins", d, null)).append('\n');

        // --- /CS abbreviations ---
        for (String[] cs : new String[][] {
            {"cs_G", "G"}, {"cs_RGB", "RGB"}, {"cs_CMYK", "CMYK"},
            {"cs_DeviceGray", "DeviceGray"}, {"cs_DeviceRGB", "DeviceRGB"},
            {"cs_DeviceCMYK", "DeviceCMYK"}, {"cs_Pattern", "Pattern"},
            {"cs_unknown", "Bogus"}
        }) {
            d = new COSDictionary();
            d.setItem(n("W"), COSInteger.get(2));
            d.setItem(n("H"), COSInteger.get(2));
            d.setItem(n("BPC"), COSInteger.get(8));
            d.setItem(n("CS"), n(cs[1]));
            sb.append(run(cs[0], d, null)).append('\n');
        }

        // /CS indexed abbreviation [/I /RGB 1 <00FF>]
        d = new COSDictionary();
        d.setItem(n("W"), COSInteger.get(2));
        d.setItem(n("H"), COSInteger.get(1));
        d.setItem(n("BPC"), COSInteger.get(8));
        COSArray idx = new COSArray();
        idx.add(n("I"));
        idx.add(n("RGB"));
        idx.add(COSInteger.get(1));
        idx.add(new COSString(new byte[] {0, 0, 0, (byte) 255, (byte) 255, (byte) 255}));
        d.setItem(n("CS"), idx);
        sb.append(run("cs_indexed_I_RGB", d, null)).append('\n');

        // /CS [/Indexed /DeviceRGB 1 <...>] full form
        d = new COSDictionary();
        d.setItem(n("W"), COSInteger.get(2));
        d.setItem(n("H"), COSInteger.get(1));
        d.setItem(n("BPC"), COSInteger.get(8));
        COSArray idx2 = new COSArray();
        idx2.add(n("Indexed"));
        idx2.add(n("DeviceRGB"));
        idx2.add(COSInteger.get(1));
        idx2.add(new COSString(new byte[] {0, 0, 0, (byte) 255, (byte) 255, (byte) 255}));
        d.setItem(n("CS"), idx2);
        sb.append(run("cs_indexed_full", d, null)).append('\n');

        // named resource colour space
        d = new COSDictionary();
        d.setItem(n("W"), COSInteger.get(2));
        d.setItem(n("H"), COSInteger.get(2));
        d.setItem(n("BPC"), COSInteger.get(8));
        d.setItem(n("CS"), n("CS0"));
        sb.append(run("cs_named_resource", d, resourcesWithRgbAlias())).append('\n');

        // named CS missing from resources
        d = new COSDictionary();
        d.setItem(n("W"), COSInteger.get(2));
        d.setItem(n("H"), COSInteger.get(2));
        d.setItem(n("BPC"), COSInteger.get(8));
        d.setItem(n("CS"), n("Missing"));
        sb.append(run("cs_named_missing", d, resourcesWithRgbAlias())).append('\n');

        // no CS, not stencil -> getColorSpace throws
        d = new COSDictionary();
        d.setItem(n("W"), COSInteger.get(2));
        d.setItem(n("H"), COSInteger.get(2));
        d.setItem(n("BPC"), COSInteger.get(8));
        sb.append(run("cs_absent_nonstencil", d, null)).append('\n');

        // --- /F abbreviations single ---
        for (String[] f : new String[][] {
            {"f_AHx", "AHx"}, {"f_A85", "A85"}, {"f_Fl", "Fl"}, {"f_RL", "RL"},
            {"f_LZW", "LZW"}
        }) {
            d = new COSDictionary();
            d.setItem(n("W"), COSInteger.get(0));
            d.setItem(n("H"), COSInteger.get(0));
            d.setItem(n("F"), n(f[1]));
            sb.append(run(f[0], d, null)).append('\n');
        }

        // /F array [/A85 /Fl]
        d = new COSDictionary();
        d.setItem(n("W"), COSInteger.get(0));
        d.setItem(n("H"), COSInteger.get(0));
        COSArray fa = new COSArray();
        fa.add(n("A85"));
        fa.add(n("Fl"));
        d.setItem(n("F"), fa);
        sb.append(run("f_array_A85_Fl", d, null)).append('\n');

        // /Filter full key single
        d = new COSDictionary();
        d.setItem(n("W"), COSInteger.get(0));
        d.setItem(n("H"), COSInteger.get(0));
        d.setItem(n("Filter"), n("FlateDecode"));
        sb.append(run("filter_full_flate", d, null)).append('\n');

        // unknown filter -> construction throw
        d = new COSDictionary();
        d.setItem(n("W"), COSInteger.get(0));
        d.setItem(n("H"), COSInteger.get(0));
        d.setItem(n("F"), n("Bogus"));
        sb.append(run("f_unknown", d, null)).append('\n');

        // DCT filter -> suffix jpg (decode of empty DCT data: capture throw-or-not)
        d = new COSDictionary();
        d.setItem(n("W"), COSInteger.get(1));
        d.setItem(n("H"), COSInteger.get(1));
        d.setItem(n("BPC"), COSInteger.get(8));
        d.setItem(n("CS"), n("RGB"));
        d.setItem(n("F"), n("DCT"));
        sb.append(run("f_dct_suffix", d, null)).append('\n');

        // CCF filter -> suffix tiff
        d = new COSDictionary();
        d.setItem(n("W"), COSInteger.get(8));
        d.setItem(n("H"), COSInteger.get(1));
        d.setItem(n("IM"), COSBoolean.TRUE);
        d.setItem(n("F"), n("CCF"));
        sb.append(run("f_ccf_suffix", d, null)).append('\n');

        // --- /BPC edge cases ---
        d = new COSDictionary();
        d.setItem(n("W"), COSInteger.get(2));
        d.setItem(n("H"), COSInteger.get(2));
        d.setItem(n("CS"), n("G"));
        sb.append(run("bpc_missing", d, null)).append('\n');

        d = new COSDictionary();
        d.setItem(n("W"), COSInteger.get(2));
        d.setItem(n("H"), COSInteger.get(2));
        d.setItem(n("BPC"), COSInteger.get(0));
        d.setItem(n("CS"), n("G"));
        sb.append(run("bpc_zero", d, null)).append('\n');

        d = new COSDictionary();
        d.setItem(n("W"), COSInteger.get(2));
        d.setItem(n("H"), COSInteger.get(2));
        d.setItem(n("BPC"), COSInteger.get(-3));
        d.setItem(n("CS"), n("G"));
        sb.append(run("bpc_negative", d, null)).append('\n');

        d = new COSDictionary();
        d.setItem(n("W"), COSInteger.get(2));
        d.setItem(n("H"), COSInteger.get(2));
        d.setItem(n("BPC"), n("NotANumber"));
        d.setItem(n("CS"), n("G"));
        sb.append(run("bpc_nonint", d, null)).append('\n');

        // --- /W /H edge cases ---
        d = new COSDictionary();
        d.setItem(n("H"), COSInteger.get(2));
        sb.append(run("w_missing", d, null)).append('\n');

        d = new COSDictionary();
        d.setItem(n("W"), COSInteger.get(0));
        d.setItem(n("H"), COSInteger.get(0));
        sb.append(run("wh_zero", d, null)).append('\n');

        d = new COSDictionary();
        d.setItem(n("W"), COSInteger.get(-5));
        d.setItem(n("H"), COSInteger.get(-7));
        sb.append(run("wh_negative", d, null)).append('\n');

        d = new COSDictionary();
        d.setItem(n("W"), new COSFloat(3.9f));
        d.setItem(n("H"), new COSFloat(2.1f));
        sb.append(run("wh_float", d, null)).append('\n');

        d = new COSDictionary();
        d.setItem(n("W"), n("Wide"));
        d.setItem(n("H"), COSString.parseHex("00"));
        sb.append(run("wh_nonint", d, null)).append('\n');

        d = new COSDictionary();
        d.setItem(n("W"), COSNull.NULL);
        d.setItem(n("H"), COSNull.NULL);
        sb.append(run("wh_null", d, null)).append('\n');

        // --- /IM stencil edge cases ---
        d = new COSDictionary();
        d.setItem(n("W"), COSInteger.get(8));
        d.setItem(n("H"), COSInteger.get(1));
        d.setItem(n("IM"), COSBoolean.TRUE);
        sb.append(run("stencil_no_bpc", d, null)).append('\n');

        // stencil with mismatched BPC=8 -> getBitsPerComponent forced to 1
        d = new COSDictionary();
        d.setItem(n("W"), COSInteger.get(8));
        d.setItem(n("H"), COSInteger.get(1));
        d.setItem(n("IM"), COSBoolean.TRUE);
        d.setItem(n("BPC"), COSInteger.get(8));
        sb.append(run("stencil_bpc8_mismatch", d, null)).append('\n');

        // stencil with explicit CS RGB (unusual) -> CS still resolved
        d = new COSDictionary();
        d.setItem(n("W"), COSInteger.get(8));
        d.setItem(n("H"), COSInteger.get(1));
        d.setItem(n("IM"), COSBoolean.TRUE);
        d.setItem(n("CS"), n("RGB"));
        sb.append(run("stencil_with_rgb", d, null)).append('\n');

        // ImageMask full key true
        d = new COSDictionary();
        d.setItem(n("W"), COSInteger.get(8));
        d.setItem(n("H"), COSInteger.get(1));
        d.setItem(n("ImageMask"), COSBoolean.TRUE);
        sb.append(run("imagemask_full", d, null)).append('\n');

        // --- /Decode arity ---
        d = new COSDictionary();
        d.setItem(n("W"), COSInteger.get(2));
        d.setItem(n("H"), COSInteger.get(2));
        d.setItem(n("BPC"), COSInteger.get(8));
        d.setItem(n("CS"), n("G"));
        COSArray dec = new COSArray();
        dec.add(COSInteger.get(1));
        dec.add(COSInteger.get(0));
        d.setItem(n("D"), dec);
        sb.append(run("decode_gray_inverted", d, null)).append('\n');

        // wrong arity decode (3 entries) -- getter returns it verbatim
        d = new COSDictionary();
        d.setItem(n("W"), COSInteger.get(2));
        d.setItem(n("H"), COSInteger.get(2));
        d.setItem(n("BPC"), COSInteger.get(8));
        d.setItem(n("CS"), n("RGB"));
        COSArray dec3 = new COSArray();
        dec3.add(COSInteger.get(0));
        dec3.add(COSInteger.get(1));
        dec3.add(COSInteger.get(0));
        d.setItem(n("Decode"), dec3);
        sb.append(run("decode_wrong_arity", d, null)).append('\n');

        // decode not an array -> getDecode returns null
        d = new COSDictionary();
        d.setItem(n("W"), COSInteger.get(2));
        d.setItem(n("H"), COSInteger.get(2));
        d.setItem(n("BPC"), COSInteger.get(8));
        d.setItem(n("CS"), n("G"));
        d.setItem(n("D"), COSInteger.get(7));
        sb.append(run("decode_not_array", d, null)).append('\n');

        // empty dict
        sb.append(run("empty_dict", new COSDictionary(), null)).append('\n');

        out.print(sb);
    }
}
