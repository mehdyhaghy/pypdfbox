import java.io.File;
import java.io.PrintStream;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.TreeSet;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.PDResources;
import org.apache.pdfbox.pdmodel.font.PDFont;
import org.apache.pdfbox.pdmodel.graphics.color.PDColorSpace;
import org.apache.pdfbox.pdmodel.graphics.pattern.PDAbstractPattern;
import org.apache.pdfbox.pdmodel.documentinterchange.markedcontent.PDPropertyList;
import org.apache.pdfbox.pdmodel.graphics.PDXObject;
import org.apache.pdfbox.pdmodel.graphics.shading.PDShading;
import org.apache.pdfbox.pdmodel.graphics.state.PDExtendedGraphicsState;

/**
 * Differential fuzz probe for the {@link PDResources} lookup / dispatch layer,
 * Apache PDFBox 3.0.7 (wave 1514, agent D).
 *
 * <p>Complements the well-formed {@code ResourceLookupProbe} (which builds one
 * valid entry per category and compares resolved classes) — none of which
 * exercise the MALFORMED {@code /Resources} subset this probe targets:
 *
 * <ul>
 *   <li>each resource sub-dictionary ({@code /Font} {@code /XObject}
 *       {@code /ColorSpace} {@code /ExtGState} {@code /Shading} {@code /Pattern}
 *       {@code /Properties}) MISSING vs WRONG-TYPE (array / string / number
 *       instead of dictionary);</li>
 *   <li>a requested name ABSENT from a present sub-dictionary;</li>
 *   <li>the named entry PRESENT but WRONG-TYPE (e.g. {@code /Font/F1} pointing
 *       at a COSName / array / number rather than a font dictionary);</li>
 *   <li>{@code getColorSpace} with the device-name shortcuts
 *       ({@code DeviceGray} / {@code DeviceRGB} / {@code DeviceCMYK} /
 *       {@code Pattern}) that resolve WITHOUT a {@code /ColorSpace} entry, plus
 *       a {@code Default*} override interaction;</li>
 *   <li>{@code getColorSpace} cache stability across two calls;</li>
 *   <li>the {@code hasColorSpace} / {@code isImageXObject} predicates and the
 *       {@code get_*_names} listings over a malformed sub-dictionary.</li>
 * </ul>
 *
 * <p>This is the RESOURCES LOOKUP/DISPATCH layer, NOT the color-space (fuzzed
 * wave 1512) or shading/pattern (wave 1513) construction internals — the focus
 * is how {@code PDResources} resolves a NAME to an object and tolerates a
 * malformed sub-dictionary.
 *
 * <p>Driven file-based: the pypdfbox sibling
 * (tests/pdmodel/oracle/test_resources_lookup_fuzz_wave1514.py) writes a
 * deterministic corpus of one-page PDFs (each page's {@code /Resources} is the
 * mutated dict) plus a {@code manifest.txt} (one case name per line, in order)
 * into a tmp dir. This probe loads each {@code <case>.pdf}, resolves the first
 * page resources, and projects a stable framed line by probing every getter
 * against a fixed set of names. Both sides read the exact same bytes on disk.
 *
 * <p>The probed name is encoded by case-name prefix so a single corpus can mix
 * categories. Every case is projected through the SAME line grammar:
 *
 * <pre>
 *   CASE &lt;name&gt; font=&lt;cls|null|ERR:X&gt; xobj=&lt;cls|null|ERR:X&gt; cs=&lt;name|null|ERR:X&gt; gs=&lt;cls|null|ERR:X&gt; sh=&lt;cls|null|ERR:X&gt; pat=&lt;cls|null|ERR:X&gt; prop=&lt;cls|null|ERR:X&gt; has=&lt;f,x,c,g,s,p,r flags&gt; names=&lt;...&gt;
 * </pre>
 *
 * <p>Where each lookup is performed against the probe name {@code "Q1"} (the
 * single key both sides install per case), {@code has} is the two
 * upstream-comparable presence predicates ({@code hasColorSpace} against the
 * case color-space name, then {@code isImageXObject} against {@code "Q1"}) as a
 * {@code 0}/{@code 1} bitstring, and {@code names} is the sorted union of all
 * seven {@code get_*_names} listings. "ERR:X" means the getter threw exception
 * class X.
 */
public final class ResourcesLookupFuzzProbe {

    static PrintStream out;

    static final COSName Q1 = COSName.getPDFName("Q1");

    static String exc(Exception e) {
        return "ERR:" + e.getClass().getSimpleName();
    }

    static String fontCell(PDResources res) {
        try {
            PDFont f = res.getFont(Q1);
            return f == null ? "null" : f.getClass().getSimpleName();
        } catch (Exception e) {
            return exc(e);
        }
    }

    static String xobjCell(PDResources res) {
        try {
            PDXObject x = res.getXObject(Q1);
            return x == null ? "null" : x.getClass().getSimpleName();
        } catch (Exception e) {
            return exc(e);
        }
    }

    /** Probe getColorSpace against the case-specified color-space name. */
    static String csCell(PDResources res, COSName name) {
        try {
            PDColorSpace cs = res.getColorSpace(name);
            return cs == null ? "null" : cs.getName();
        } catch (Exception e) {
            return exc(e);
        }
    }

    static String gsCell(PDResources res) {
        try {
            PDExtendedGraphicsState gs = res.getExtGState(Q1);
            return gs == null ? "null" : gs.getClass().getSimpleName();
        } catch (Exception e) {
            return exc(e);
        }
    }

    static String shCell(PDResources res) {
        try {
            PDShading sh = res.getShading(Q1);
            return sh == null ? "null" : sh.getClass().getSimpleName();
        } catch (Exception e) {
            return exc(e);
        }
    }

    static String patCell(PDResources res) {
        try {
            PDAbstractPattern p = res.getPattern(Q1);
            return p == null ? "null" : p.getClass().getSimpleName();
        } catch (Exception e) {
            return exc(e);
        }
    }

    static String propCell(PDResources res) {
        try {
            PDPropertyList p = res.getProperties(Q1);
            return p == null ? "null" : p.getClass().getSimpleName();
        } catch (Exception e) {
            return exc(e);
        }
    }

    /**
     * The only upstream-comparable presence predicate: {@code hasColorSpace}
     * (probed against the case color-space name) and {@code isImageXObject}
     * (probed against "Q1"). PDFBox 3.0.7 exposes no other {@code has*}
     * predicate; pypdfbox's additional {@code has_*}/{@code clear_*} helpers
     * are covered by the Python-side unit assertions, not this differential
     * line.
     */
    static String hasCell(PDResources res, COSName csName) {
        StringBuilder sb = new StringBuilder();
        sb.append(bit(() -> res.hasColorSpace(csName)));
        sb.append(bit(() -> res.isImageXObject(Q1)));
        return sb.toString();
    }

    interface BoolSupplier {
        boolean get();
    }

    static String bit(BoolSupplier s) {
        try {
            return s.get() ? "1" : "0";
        } catch (Exception e) {
            return "E";
        }
    }

    static String namesCell(PDResources res) {
        TreeSet<String> set = new TreeSet<>();
        addNames(set, res.getFontNames());
        addNames(set, res.getXObjectNames());
        addNames(set, res.getColorSpaceNames());
        addNames(set, res.getExtGStateNames());
        addNames(set, res.getShadingNames());
        addNames(set, res.getPatternNames());
        addNames(set, res.getPropertiesNames());
        List<String> list = new ArrayList<>(set);
        return list.isEmpty() ? "-" : String.join("|", list);
    }

    static void addNames(TreeSet<String> set, Iterable<COSName> names) {
        try {
            for (COSName n : names) {
                set.add(n.getName());
            }
        } catch (Exception ignored) {
            // a malformed sub-dict that throws during key enumeration
            // contributes nothing — best-effort union.
        }
    }

    /**
     * The color-space probe name depends on the case: device-shortcut cases
     * probe the well-known name; everything else probes "Q1" (the installed
     * key). The prefix convention keeps a single corpus self-describing.
     */
    static COSName csProbeName(String name) {
        if (name.startsWith("cs_device_gray")) {
            return COSName.getPDFName("DeviceGray");
        }
        if (name.startsWith("cs_device_rgb")) {
            return COSName.getPDFName("DeviceRGB");
        }
        if (name.startsWith("cs_device_cmyk")) {
            return COSName.getPDFName("DeviceCMYK");
        }
        if (name.startsWith("cs_pattern_shortcut")) {
            return COSName.getPDFName("Pattern");
        }
        if (name.startsWith("cs_g_short")) {
            return COSName.getPDFName("G");
        }
        if (name.startsWith("cs_absent_nondevice")) {
            return COSName.getPDFName("Nope");
        }
        return Q1;
    }

    static void runCase(File dir, String name) {
        File pdf = new File(dir, name + ".pdf");
        StringBuilder sb = new StringBuilder();
        sb.append("CASE ").append(name).append(' ');
        PDDocument doc = null;
        try {
            doc = Loader.loadPDF(pdf);
            PDPage page = doc.getPage(0);
            PDResources res = page.getResources();
            if (res == null) {
                sb.append("font=NORES xobj=NORES cs=NORES gs=NORES sh=NORES "
                        + "pat=NORES prop=NORES has=NORES names=NORES");
            } else {
                sb.append("font=").append(fontCell(res));
                sb.append(" xobj=").append(xobjCell(res));
                sb.append(" cs=").append(csCell(res, csProbeName(name)));
                sb.append(" gs=").append(gsCell(res));
                sb.append(" sh=").append(shCell(res));
                sb.append(" pat=").append(patCell(res));
                sb.append(" prop=").append(propCell(res));
                sb.append(" has=").append(hasCell(res, csProbeName(name)));
                sb.append(" names=").append(namesCell(res));
            }
        } catch (Exception e) {
            sb.append("font=LOAD:").append(e.getClass().getSimpleName())
                    .append(" xobj=LOAD cs=LOAD gs=LOAD sh=LOAD pat=LOAD "
                            + "prop=LOAD has=LOAD names=LOAD");
        } finally {
            if (doc != null) {
                try {
                    doc.close();
                } catch (Exception ignored) {
                    // best-effort close
                }
            }
        }
        out.println(sb.toString());
    }

    public static void main(String[] args) throws Exception {
        out = new PrintStream(System.out, true, "UTF-8");
        File dir = new File(args[0]);
        File manifest = new File(dir, "manifest.txt");
        String[] names =
                new String(java.nio.file.Files.readAllBytes(manifest.toPath()),
                                java.nio.charset.StandardCharsets.UTF_8)
                        .split("\n");
        Arrays.stream(names)
                .map(String::trim)
                .filter(s -> !s.isEmpty())
                .forEach(name -> runCase(dir, name));
    }
}
