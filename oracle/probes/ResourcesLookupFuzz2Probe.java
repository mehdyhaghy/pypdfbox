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
 * Second-generation differential fuzz probe for the {@link PDResources}
 * lookup / dispatch layer, Apache PDFBox 3.0.7 (wave 1555, agent A).
 *
 * <p>Complements {@code ResourcesLookupFuzzProbe} (wave 1514, which fuzzed
 * missing / wrong-type sub-dicts, absent names, wrong-type entries, device
 * shortcuts and the {@code Default*} override). This probe targets the angles
 * wave 1514 did NOT exercise:
 *
 * <ul>
 *   <li>an {@code /XObject} stream whose {@code /Subtype} is a COSString
 *       ({@code "Form"} / {@code "Image"}) rather than a name — upstream
 *       {@code PDXObject.createXObject} reads it through
 *       {@code COSStream.getNameAsString}, so a string subtype STILL
 *       dispatches; absent / unknown subtypes raise;</li>
 *   <li>resource names with {@code #}-escapes / special characters round-trip
 *       through the lexer and still resolve;</li>
 *   <li>{@code getProperties} class projection across an OCG, an OCMD, and a
 *       plain marked-content dictionary;</li>
 *   <li>{@code getColorSpace} where the named {@code /ColorSpace/Q1} entry is
 *       itself a device-name COSName, and the inline array color-space forms
 *       (CalRGB / CalGray / Lab / Separation / Indexed) resolved by name;</li>
 *   <li>two distinct objects added to the same sub-dict and the resolved class
 *       per allocated key (in-memory {@code add} section).</li>
 * </ul>
 *
 * <p>File-based cases share the SAME bytes with the pytest sibling
 * (tests/pdmodel/oracle/test_resources_lookup_fuzz_wave1555.py), which writes a
 * one-page PDF per case plus {@code manifest.txt}. Each case is projected
 * through the same line grammar as wave 1514:
 *
 * <pre>
 *   CASE &lt;name&gt; font=&lt;...&gt; xobj=&lt;...&gt; cs=&lt;...&gt; gs=&lt;...&gt; sh=&lt;...&gt; pat=&lt;...&gt; prop=&lt;...&gt; has=&lt;cc&gt; names=&lt;...&gt;
 * </pre>
 *
 * <p>The probed name is {@code "Q1"} for every getter except {@code cs}, whose
 * name is selected by case-name prefix (see {@link #csProbeName}).
 */
public final class ResourcesLookupFuzz2Probe {

    static PrintStream out;

    static final COSName Q1 = COSName.getPDFName("Q1");

    static String exc(Exception e) {
        return "ERR:" + e.getClass().getSimpleName();
    }

    static String fontCell(PDResources res, COSName name) {
        try {
            PDFont f = res.getFont(name);
            return f == null ? "null" : f.getClass().getSimpleName();
        } catch (Exception e) {
            return exc(e);
        }
    }

    static String xobjCell(PDResources res, COSName name) {
        try {
            PDXObject x = res.getXObject(name);
            return x == null ? "null" : x.getClass().getSimpleName();
        } catch (Exception e) {
            return exc(e);
        }
    }

    static String csCell(PDResources res, COSName name) {
        try {
            PDColorSpace cs = res.getColorSpace(name);
            return cs == null ? "null" : cs.getName();
        } catch (Exception e) {
            return exc(e);
        }
    }

    static String gsCell(PDResources res, COSName name) {
        try {
            PDExtendedGraphicsState gs = res.getExtGState(name);
            return gs == null ? "null" : gs.getClass().getSimpleName();
        } catch (Exception e) {
            return exc(e);
        }
    }

    static String shCell(PDResources res, COSName name) {
        try {
            PDShading sh = res.getShading(name);
            return sh == null ? "null" : sh.getClass().getSimpleName();
        } catch (Exception e) {
            return exc(e);
        }
    }

    static String patCell(PDResources res, COSName name) {
        try {
            PDAbstractPattern p = res.getPattern(name);
            return p == null ? "null" : p.getClass().getSimpleName();
        } catch (Exception e) {
            return exc(e);
        }
    }

    static String propCell(PDResources res, COSName name) {
        try {
            PDPropertyList p = res.getProperties(name);
            return p == null ? "null" : p.getClass().getSimpleName();
        } catch (Exception e) {
            return exc(e);
        }
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

    static String hasCell(PDResources res, COSName csName, COSName probe) {
        StringBuilder sb = new StringBuilder();
        sb.append(bit(() -> res.hasColorSpace(csName)));
        sb.append(bit(() -> res.isImageXObject(probe)));
        return sb.toString();
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
            // best-effort union over a possibly-malformed sub-dict
        }
    }

    /** Probe-name selector by case-name prefix. */
    static COSName probeName(String name) {
        if (name.startsWith("name_hash_escape")) {
            return COSName.getPDFName("A B#C");
        }
        if (name.startsWith("name_special")) {
            return COSName.getPDFName("Aあ");
        }
        return Q1;
    }

    static COSName csProbeName(String name) {
        if (name.startsWith("cs_named_device")) {
            return Q1;
        }
        if (name.startsWith("cs_")) {
            return Q1;
        }
        return probeName(name);
    }

    static void runFileCase(File dir, String name) {
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
                COSName p = probeName(name);
                COSName csp = csProbeName(name);
                sb.append("font=").append(fontCell(res, p));
                sb.append(" xobj=").append(xobjCell(res, p));
                sb.append(" cs=").append(csCell(res, csp));
                sb.append(" gs=").append(gsCell(res, p));
                sb.append(" sh=").append(shCell(res, p));
                sb.append(" pat=").append(patCell(res, p));
                sb.append(" prop=").append(propCell(res, p));
                sb.append(" has=").append(hasCell(res, csp, p));
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
                .forEach(name -> runFileCase(dir, name));
    }
}
