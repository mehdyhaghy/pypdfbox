import java.io.File;
import java.io.PrintStream;
import java.util.Arrays;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.PDResources;
import org.apache.pdfbox.pdmodel.common.function.PDFunction;
import org.apache.pdfbox.pdmodel.graphics.shading.PDShading;
import org.apache.pdfbox.pdmodel.graphics.shading.PDShadingType1;
import org.apache.pdfbox.pdmodel.graphics.shading.PDShadingType2;
import org.apache.pdfbox.pdmodel.graphics.shading.PDShadingType3;

/**
 * Differential fuzz probe for the type-specific geometry / function accessors
 * of {@link PDShadingType1} (function-based), {@link PDShadingType2} (axial),
 * and {@link PDShadingType3} (radial), Apache PDFBox 3.0.7 (wave 1538, agent C).
 *
 * <p>Distinct angle from the generic {@code ShadingPatternFuzzProbe} (which
 * projects {@code getShadingType} / {@code getColorSpace} / raw COS key arity):
 * this probe drives the <em>typed</em> accessors that each concrete subclass
 * exposes and that callers actually consume —
 * {@code PDShadingType1.getDomain()} / {@code getMatrix()} / {@code getFunction()};
 * {@code PDShadingType2/3.getCoords()} / {@code getDomain()} / {@code getExtend()}
 * / {@code getFunction()}. Each upstream getter delegates to
 * {@code getCOSArray(name)} (returns the COSArray, or {@code null} when the
 * entry is absent OR not a COSArray — no spec-default materialization), so a
 * missing / wrong-length / wrong-type entry surfaces as {@code null} or as the
 * actual arity, never a synthesized default. {@code getFunction()} routes any
 * non-null {@code /Function} through {@code PDFunction.create}.
 *
 * <p>Driven file-based: the pypdfbox sibling
 * (tests/pdmodel/graphics/shading/oracle/test_axial_radial_shading_fuzz_wave1538.py)
 * writes a one-page PDF per case (the mutated shading dict installed as
 * resource {@code /Shading/Sh1}) plus a {@code manifest.txt} (one case name per
 * line, in order) into a tmp directory. Both sides read the same bytes.
 *
 * <p>Line grammar (one per case, manifest order):
 * <pre>
 *   CASE &lt;name&gt; type=&lt;n|ERR&gt; class=&lt;simpleName|null&gt; coords=&lt;arr_n|null|n/a&gt; domain=&lt;arr_n|null&gt; extend=&lt;arr_n|null|n/a&gt; matrix=&lt;arr_n|null|n/a&gt; function=&lt;simpleName|null|ERR&gt;
 * </pre>
 *
 * <p>{@code coords} / {@code matrix} are {@code n/a} for the type that lacks
 * the accessor (Type1 has no getCoords; Types 2/3 have no getMatrix).
 */
public final class AxialRadialShadingFuzzProbe {

    static PrintStream out;

    static String arrArity(COSArray a) {
        return a == null ? "null" : "arr" + a.size();
    }

    static String funcProjection(PDShading shading) {
        try {
            PDFunction f = shading.getFunction();
            return f == null ? "null" : f.getClass().getSimpleName();
        } catch (Exception e) {
            return "ERR:" + e.getClass().getSimpleName();
        }
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
            PDShading shading = res.getShading(COSName.getPDFName("Sh1"));
            if (shading == null) {
                sb.append("type=null class=null coords=null domain=null "
                        + "extend=null matrix=null function=null");
            } else {
                String t;
                try {
                    t = Integer.toString(shading.getShadingType());
                } catch (Exception e) {
                    t = "ERR";
                }
                String coords;
                String domain;
                String extend;
                String matrix;
                if (shading instanceof PDShadingType1) {
                    PDShadingType1 s1 = (PDShadingType1) shading;
                    coords = "n/a";
                    domain = arrArity(s1.getDomain());
                    extend = "n/a";
                    // getMatrix() returns a non-null Matrix even for absent /
                    // wrong-length / non-numeric (Matrix.createMatrix falls
                    // back to identity); project "ok" to record that contract
                    // uniformly without depending on the Matrix vs COSArray
                    // return-type difference.
                    matrix = s1.getMatrix() == null ? "null" : "ok";
                } else if (shading instanceof PDShadingType3) {
                    PDShadingType3 s3 = (PDShadingType3) shading;
                    coords = arrArity(s3.getCoords());
                    domain = arrArity(s3.getDomain());
                    extend = arrArity(s3.getExtend());
                    matrix = "n/a";
                } else if (shading instanceof PDShadingType2) {
                    PDShadingType2 s2 = (PDShadingType2) shading;
                    coords = arrArity(s2.getCoords());
                    domain = arrArity(s2.getDomain());
                    extend = arrArity(s2.getExtend());
                    matrix = "n/a";
                } else {
                    coords = "n/a";
                    domain = "n/a";
                    extend = "n/a";
                    matrix = "n/a";
                }
                sb.append("type=").append(t);
                sb.append(" class=").append(shading.getClass().getSimpleName());
                sb.append(" coords=").append(coords);
                sb.append(" domain=").append(domain);
                sb.append(" extend=").append(extend);
                sb.append(" matrix=").append(matrix);
                sb.append(" function=").append(funcProjection(shading));
            }
        } catch (Exception e) {
            sb.append("type=ERR class=ERR:")
                    .append(e.getClass().getSimpleName())
                    .append(" coords=ERR domain=ERR extend=ERR matrix=ERR function=ERR");
        } finally {
            close(doc);
        }
        out.println(sb.toString());
    }

    static void close(PDDocument doc) {
        if (doc != null) {
            try {
                doc.close();
            } catch (Exception ignored) {
                // best-effort close
            }
        }
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
