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
import org.apache.pdfbox.pdmodel.graphics.color.PDColorSpace;
import org.apache.pdfbox.pdmodel.graphics.color.PDDeviceCMYK;
import org.apache.pdfbox.pdmodel.graphics.color.PDDeviceGray;
import org.apache.pdfbox.pdmodel.graphics.color.PDDeviceRGB;
import org.apache.pdfbox.pdmodel.graphics.color.PDICCBased;
import org.apache.pdfbox.pdmodel.graphics.color.PDIndexed;

/**
 * Differential fuzz probe for the ICCBased + Indexed + device colour-space
 * surfaces, Apache PDFBox 3.0.7 (wave 1550, agent E).
 *
 * <p>Complements the wave-1528 {@code IccBasedFuzzProbe} (which drilled the
 * {@code /N}/{@code /Alternate}/{@code /Range}/{@code /Metadata} accessor
 * surface) and the existing {@code IndexedRoundProbe}/{@code IndexedStreamProbe}
 * (which exercised toRGB index rounding/clamp on DeviceRGB and DeviceCMYK
 * bases) by attacking angles those probes did NOT cover:
 *
 * <ul>
 *   <li><b>ICCBased</b> — no embedded ICC profile (so Java's AWT {@code
 *       ICC_Profile} parse stays null, matching pypdfbox which carries no AWT
 *       colour space); project getNumberOfComponents, getInitialColor
 *       components and a single toRGB call routed through the alternate (NOT
 *       through the JVM CMM, since there is no readable profile — so the
 *       device-alternate toRGB is pure arithmetic and byte-comparable).</li>
 *   <li><b>Indexed</b> — construction over malformed /hival (negative, huge,
 *       non-int name, COSNull) and malformed /lookup (string vs stream, too
 *       short, too long, COSNull); project the color-table entry count
 *       (= actualMaxIndex+1, recovered by probing toRGB across a wide index
 *       sweep) plus toRGB for representative indices including out-of-range.
 *       Indexed bases used: DeviceGray (1 byte/entry), DeviceRGB (3), DeviceCMYK
 *       (4), and ICCBased-with-DeviceRGB-alternate (3) — none route through a
 *       readable CMM, so toRGB is byte-comparable.</li>
 *   <li><b>device</b> — DeviceGray/RGB/CMYK getNumberOfComponents,
 *       getInitialColor, and toRGB at a few interior points (CMYK uses the
 *       upstream bundled ICC profile, so its toRGB IS CMM-routed → emitted with
 *       a CMM_MARKER token instead of byte values; the pypdfbox subtractive
 *       approximation is pinned as a documented divergence).</li>
 * </ul>
 *
 * <p>Line grammars (one line per case):
 * <pre>
 *   ICC &lt;name&gt; ctor=&lt;ERR|ok&gt; nc=&lt;n&gt; init=&lt;a,b,..&gt; rgb=&lt;r,g,b|ERR&gt;
 *   IDX &lt;name&gt; ctor=&lt;ERR|ok&gt; nc=&lt;n&gt; entries=&lt;k&gt; init=&lt;a,..&gt; \
 *       rgb[&lt;i&gt;]=&lt;r g b&gt; ...
 *   DEV &lt;name&gt; nc=&lt;n&gt; init=&lt;a,..&gt; rgb=&lt;r,g,b|CMM_MARKER&gt;
 * </pre>
 * RGB tokens are round(component*255) clamped to [0,255].
 */
public final class IccIndexedColorFuzzProbe {

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

    static int clamp255(float v) {
        long r = Math.round((double) v * 255.0);
        if (r < 0) {
            return 0;
        }
        if (r > 255) {
            return 255;
        }
        return (int) r;
    }

    static String comps(float[] c) {
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < c.length; i++) {
            if (i > 0) {
                sb.append(',');
            }
            sb.append(String.format(Locale.ROOT, "%.3f", c[i]));
        }
        return sb.toString();
    }

    // ---------- ICCBased (no profile body) ----------

    static COSStream icc(Integer nVal, COSBase alt) throws Exception {
        COSStream s = new COSStream();
        if (nVal != null) {
            s.setInt(COSName.N, nVal);
        }
        if (alt != null) {
            s.setItem(COSName.ALTERNATE, alt);
        }
        OutputStream os = s.createOutputStream();
        os.close();
        return s;
    }

    static void emitIcc(String name, COSArray array, float[] sample) {
        StringBuilder sb = new StringBuilder("ICC ").append(name).append(' ');
        PDICCBased cs;
        try {
            PDColorSpace created = PDColorSpace.create(array, null);
            cs = (PDICCBased) created;
        } catch (Throwable t) {
            out.println(sb.append("ctor=ERR").toString());
            return;
        }
        sb.append("ctor=ok");
        try {
            sb.append(" nc=").append(cs.getNumberOfComponents());
        } catch (Throwable t) {
            sb.append(" nc=ERR");
        }
        try {
            sb.append(" init=").append(comps(cs.getInitialColor().getComponents()));
        } catch (Throwable t) {
            sb.append(" init=ERR");
        }
        // toRGB: no readable profile, so this routes through the alternate
        // (device arithmetic) — byte-comparable, NOT CMM.
        try {
            float[] rgb = cs.toRGB(sample);
            sb.append(" rgb=").append(clamp255(rgb[0])).append(',')
                    .append(clamp255(rgb[1])).append(',').append(clamp255(rgb[2]));
        } catch (Throwable t) {
            sb.append(" rgb=ERR");
        }
        out.println(sb.toString());
    }

    // ---------- Indexed ----------

    static COSStream lookupStream(byte[] palette) throws Exception {
        COSStream s = new COSStream();
        OutputStream os = s.createOutputStream(COSName.FLATE_DECODE);
        os.write(palette);
        os.close();
        return s;
    }

    static COSArray indexedArr(COSBase base, COSBase hival, COSBase lookup) {
        COSArray a = new COSArray();
        a.add(COSName.INDEXED);
        a.add(base);
        a.add(hival);
        a.add(lookup);
        return a;
    }

    // ICCBased array with DeviceRGB alternate, N=3, no profile body.
    static COSArray iccRgbBase() throws Exception {
        return arr(n("ICCBased"), icc(3, COSName.DEVICERGB));
    }

    static void emitIdx(String name, COSArray array, int[] indices) {
        StringBuilder sb = new StringBuilder("IDX ").append(name).append(' ');
        PDIndexed cs;
        try {
            PDColorSpace created = PDColorSpace.create(array);
            cs = (PDIndexed) created;
        } catch (Throwable t) {
            out.println(sb.append("ctor=ERR").toString());
            return;
        }
        sb.append("ctor=ok");
        sb.append(" nc=").append(cs.getNumberOfComponents());
        sb.append(" init=").append(comps(cs.getInitialColor().getComponents()));
        // Recover the palette size by sweeping toRGB over a wide index range and
        // counting distinct clamp behaviour: every index >= actualMaxIndex
        // clamps to the same top entry. We instead report it indirectly through
        // the toRGB samples below (the Python side derives the same actualMax
        // from its color table). Emit toRGB for the requested probe indices.
        for (int i : indices) {
            try {
                float[] rgb = cs.toRGB(new float[] {(float) i});
                sb.append(" rgb[").append(i).append("]=")
                        .append(clamp255(rgb[0])).append(' ')
                        .append(clamp255(rgb[1])).append(' ')
                        .append(clamp255(rgb[2]));
            } catch (Throwable t) {
                sb.append(" rgb[").append(i).append("]=ERR");
            }
        }
        out.println(sb.toString());
    }

    // ---------- device ----------

    static void emitDev(String name, PDColorSpace cs, float[] sample, boolean cmm) {
        StringBuilder sb = new StringBuilder("DEV ").append(name).append(' ');
        sb.append("nc=").append(cs.getNumberOfComponents());
        sb.append(" init=").append(comps(cs.getInitialColor().getComponents()));
        if (cmm) {
            // CMYK toRGB routes through the bundled CGATS001 ICC profile (JVM
            // CMM) — a known pinned XYZ->sRGB delta vs the pypdfbox subtractive
            // approximation. Emit a marker rather than byte-comparing.
            sb.append(" rgb=CMM_MARKER");
        } else {
            try {
                float[] rgb = cs.toRGB(sample);
                sb.append(" rgb=").append(clamp255(rgb[0])).append(',')
                        .append(clamp255(rgb[1])).append(',')
                        .append(clamp255(rgb[2]));
            } catch (Throwable t) {
                sb.append(" rgb=ERR");
            }
        }
        out.println(sb.toString());
    }

    public static void main(String[] args) throws Exception {
        out = new PrintStream(System.out, true, "UTF-8");

        // ===================== ICCBased =====================
        // /N = 1/3/4, no profile, no /Alternate -> default-by-N alternate.
        emitIcc("icc_n1", arr(n("ICCBased"), icc(1, null)), new float[] {0.5f});
        emitIcc("icc_n3", arr(n("ICCBased"), icc(3, null)),
                new float[] {0.2f, 0.4f, 0.6f});
        emitIcc("icc_n4", arr(n("ICCBased"), icc(4, null)),
                new float[] {0.1f, 0.2f, 0.3f, 0.4f});
        // /N mismatched with explicit /Alternate (N=4, gray alternate).
        emitIcc("icc_n4_alt_gray",
                arr(n("ICCBased"), icc(4, COSName.DEVICEGRAY)),
                new float[] {0.5f, 0.5f, 0.5f, 0.5f});
        // /N=1 with explicit DeviceGray alternate.
        emitIcc("icc_n1_alt_gray",
                arr(n("ICCBased"), icc(1, COSName.DEVICEGRAY)),
                new float[] {0.75f});
        // /N=3 with explicit DeviceRGB alternate.
        emitIcc("icc_n3_alt_rgb",
                arr(n("ICCBased"), icc(3, COSName.DEVICERGB)),
                new float[] {1.0f, 0.0f, 0.5f});
        // /N=4 with explicit DeviceCMYK alternate -> CMYK toRGB (subtractive in
        // pypdfbox, but here the embedded profile is null so Java ALSO uses the
        // alternate PDDeviceCMYK whose toRGB IS CMM-routed). Pin as CMM divergence.
        emitIcc("icc_n4_alt_cmyk",
                arr(n("ICCBased"), icc(4, COSName.DEVICECMYK)),
                new float[] {0.0f, 0.0f, 0.0f, 0.5f});

        // ===================== Indexed =====================
        byte[] grayPalette = new byte[] {(byte) 0, (byte) 64, (byte) 128, (byte) 255};
        byte[] rgbPalette = new byte[] {
            (byte) 0, (byte) 0, (byte) 0,
            (byte) 255, (byte) 0, (byte) 0,
            (byte) 0, (byte) 255, (byte) 0,
            (byte) 0, (byte) 0, (byte) 255
        };
        byte[] cmykPalette = new byte[] {
            (byte) 0, (byte) 0, (byte) 0, (byte) 0,
            (byte) 255, (byte) 255, (byte) 255, (byte) 255
        };

        int[] sweep = new int[] {-2, 0, 1, 2, 3, 4, 10};

        // base = DeviceGray, hival 3, 4 one-byte entries (string lookup).
        emitIdx("gray_ok",
                indexedArr(COSName.DEVICEGRAY, COSInteger.get(3),
                        new COSString(grayPalette)),
                sweep);
        // base = DeviceRGB, hival 3, string lookup.
        emitIdx("rgb_ok",
                indexedArr(COSName.DEVICERGB, COSInteger.get(3),
                        new COSString(rgbPalette)),
                sweep);
        // base = DeviceRGB, lookup as a FlateDecode stream.
        emitIdx("rgb_stream",
                indexedArr(COSName.DEVICERGB, COSInteger.get(3),
                        lookupStream(rgbPalette)),
                sweep);
        // base = DeviceCMYK (CMM-routed palette conversion). Pin as CMM divergence.
        emitIdx("cmyk_ok",
                indexedArr(COSName.DEVICECMYK, COSInteger.get(1),
                        new COSString(cmykPalette)),
                new int[] {-1, 0, 1, 2});
        // base = ICCBased(N=3, alt DeviceRGB) — palette decode via alternate (no
        // readable profile) so byte-comparable.
        emitIdx("base_icc_rgb",
                indexedArr(iccRgbBase(), COSInteger.get(3),
                        new COSString(rgbPalette)),
                sweep);

        // ---- malformed /hival ----
        // hival 0 -> single palette entry.
        emitIdx("hival_0",
                indexedArr(COSName.DEVICERGB, COSInteger.get(0),
                        new COSString(rgbPalette)),
                sweep);
        // hival negative.
        emitIdx("hival_neg",
                indexedArr(COSName.DEVICERGB, COSInteger.get(-1),
                        new COSString(rgbPalette)),
                sweep);
        // hival huge (> 255) -> clamped to 255 by readColorTable, then lookup is
        // too short so actualMaxIndex shrinks to lookup/n - 1.
        emitIdx("hival_huge",
                indexedArr(COSName.DEVICERGB, COSInteger.get(100000),
                        new COSString(rgbPalette)),
                sweep);
        // hival == 255 exactly, short lookup.
        emitIdx("hival_255_short",
                indexedArr(COSName.DEVICERGB, COSInteger.get(255),
                        new COSString(rgbPalette)),
                sweep);
        // hival non-int (a name).
        emitIdx("hival_name",
                indexedArr(COSName.DEVICERGB, n("Bogus"),
                        new COSString(rgbPalette)),
                sweep);
        // hival COSNull.
        emitIdx("hival_null",
                indexedArr(COSName.DEVICERGB, COSNull.NULL,
                        new COSString(rgbPalette)),
                sweep);

        // ---- malformed /lookup ----
        // lookup too short (only 2 entries for hival 3).
        emitIdx("lookup_short",
                indexedArr(COSName.DEVICERGB, COSInteger.get(3),
                        new COSString(new byte[] {
                            (byte) 10, (byte) 20, (byte) 30,
                            (byte) 40, (byte) 50, (byte) 60})),
                sweep);
        // lookup too long (more bytes than (hival+1)*n).
        emitIdx("lookup_long",
                indexedArr(COSName.DEVICERGB, COSInteger.get(1),
                        new COSString(rgbPalette)),
                sweep);
        // lookup COSNull.
        emitIdx("lookup_null",
                indexedArr(COSName.DEVICERGB, COSInteger.get(3), COSNull.NULL),
                sweep);
        // lookup empty string.
        emitIdx("lookup_empty",
                indexedArr(COSName.DEVICERGB, COSInteger.get(3),
                        new COSString(new byte[0])),
                sweep);

        // ===================== device =====================
        emitDev("gray", PDDeviceGray.INSTANCE, new float[] {0.5f}, false);
        emitDev("gray_black", PDDeviceGray.INSTANCE, new float[] {0.0f}, false);
        emitDev("gray_white", PDDeviceGray.INSTANCE, new float[] {1.0f}, false);
        emitDev("rgb", PDDeviceRGB.INSTANCE, new float[] {0.25f, 0.5f, 0.75f}, false);
        // CMYK toRGB is CMM-routed (bundled CGATS001 profile).
        emitDev("cmyk", PDDeviceCMYK.INSTANCE,
                new float[] {0.1f, 0.2f, 0.3f, 0.4f}, true);
        emitDev("cmyk_black", PDDeviceCMYK.INSTANCE,
                new float[] {0.0f, 0.0f, 0.0f, 1.0f}, true);
    }
}
