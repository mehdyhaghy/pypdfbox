import java.io.File;
import java.io.PrintStream;
import java.util.Arrays;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.PDResources;
import org.apache.pdfbox.pdmodel.common.PDRange;
import org.apache.pdfbox.pdmodel.common.PDRectangle;
import org.apache.pdfbox.pdmodel.common.function.PDFunction;
import org.apache.pdfbox.pdmodel.graphics.shading.PDShading;
import org.apache.pdfbox.pdmodel.graphics.shading.PDShadingType4;
import org.apache.pdfbox.pdmodel.graphics.shading.PDShadingType5;
import org.apache.pdfbox.pdmodel.graphics.shading.PDShadingType6;
import org.apache.pdfbox.pdmodel.graphics.shading.PDShadingType7;

/**
 * Differential fuzz probe for the dictionary-accessor surface of the mesh
 * shading types — {@link PDShadingType4} (free-form Gouraud triangle),
 * {@link PDShadingType5} (lattice-form Gouraud triangle), {@link PDShadingType6}
 * (Coons patch), {@link PDShadingType7} (tensor-product patch) — against Apache
 * PDFBox 3.0.7 (wave 1543, agent D).
 *
 * <p>Distinct angle from the existing shading probes:
 * <ul>
 *   <li>{@code AxialRadialShadingFuzzProbe} drives Types 1/2/3 (coords / domain
 *       / extend / matrix);</li>
 *   <li>{@code MeshGouraudFlagProbe} / {@code MeshVertexDumpProbe} dump decoded
 *       triangle geometry;</li>
 *   <li>{@code PatchMeshDecodeProbe} / {@code PatchMeshFlagProbe} dump decoded
 *       Coons / tensor patch geometry.</li>
 * </ul>
 * This probe instead fuzzes the <em>mesh metadata accessors</em> that the
 * decode paths read first and that callers consume to validate a stream before
 * rasterizing: {@code getShadingType}, {@code getBitsPerCoordinate},
 * {@code getBitsPerComponent}, {@code getBitsPerFlag} (Type 4 typed accessor;
 * Types 5/6/7 via the raw COS int), {@code getVerticesPerRow} (Type 5),
 * {@code getDecodeForParameter} (off-by-one arity contract +
 * {@code getMin}/{@code getMax} access), {@code getNumberOfColorComponents},
 * {@code getBackground}, {@code getBBox}, {@code getAntiAlias},
 * {@code getFunction}.
 *
 * <p>Notable upstream contracts this probe pins:
 * <ul>
 *   <li>{@code getBits*} delegate to {@code COSDictionary.getInt(name)} which
 *       defaults to {@code -1} (absent / non-int), with NO legal-value
 *       validation — an invalid {@code /BitsPerCoordinate} like 7 or 64 is
 *       returned verbatim.</li>
 *   <li>{@code getDecodeForParameter(p)} returns a non-null {@link PDRange}
 *       when {@code decode.size() >= 2*p + 1} (NOT {@code 2*p + 2}). The
 *       {@code PDRange} is lazy: {@code getMin()} reads index {@code 2*p},
 *       {@code getMax()} reads {@code 2*p + 1}. So at the exact boundary
 *       {@code size == 2*p + 1} the range is non-null and {@code getMin()}
 *       works but {@code getMax()} throws
 *       {@code IndexOutOfBoundsException}.</li>
 *   <li>{@code getBBox()} builds a {@link PDRectangle} from ANY non-null
 *       {@code /BBox} COSArray (no size-4 guard); a non-array {@code /BBox}
 *       yields null (getCOSArray returns null for non-arrays).</li>
 *   <li>{@code getBackground()} / the decode array use
 *       {@code getCOSArray(name)}: the stored COSArray or null (absent /
 *       wrong type) — no spec-default materialization.</li>
 * </ul>
 *
 * <p>Driven file-based, mirroring {@code AxialRadialShadingFuzzProbe}: the
 * pypdfbox sibling
 * (tests/pdmodel/graphics/shading/oracle/test_mesh_shading_fuzz_wave1543.py)
 * writes a one-page PDF per case (mutated shading dict / stream installed as
 * resource {@code /Shading/Sh1}) plus a {@code manifest.txt} (one case name per
 * line, in order) into a tmp dir. Both sides read the same bytes.
 *
 * <p>Line grammar (one per case, manifest order):
 * <pre>
 *   CASE &lt;name&gt; type=&lt;n|ERR&gt; class=&lt;simpleName|null&gt;
 *        bpc=&lt;n&gt; bcomp=&lt;n&gt; bflag=&lt;n&gt; vpr=&lt;n|n/a&gt;
 *        ncc=&lt;n|ERR&gt; dec=&lt;arr_n|null&gt;
 *        d0=&lt;okMM|min|null|ERR&gt; dc=&lt;okMM|min|null|ERR&gt;
 *        bg=&lt;arr_n|null&gt; bbox=&lt;rect|null&gt; aa=&lt;true|false&gt;
 *        function=&lt;simpleName|null|ERR&gt;
 * </pre>
 * where {@code d0} is decode-parameter 0 (the x range) and {@code dc} is the
 * first colour-component range (parameter 2). {@code okMM} = both getMin and
 * getMax succeed; {@code min} = getMin works but getMax throws; {@code null} =
 * getDecodeForParameter returned null; {@code ERR:*} = getMin itself threw.
 */
public final class MeshShadingFuzzProbe {

    static PrintStream out;

    static final COSName BITS_PER_FLAG = COSName.getPDFName("BitsPerFlag");

    static String arrArity(COSArray a) {
        return a == null ? "null" : "arr" + a.size();
    }

    /** Project a decode parameter the way a caller actually reads it: resolve
     * the PDRange (null check), then probe getMin / getMax independently. */
    static String decodeParam(PDShading shading, int param) {
        PDRange range;
        try {
            range = invokeGetDecodeForParameter(shading, param);
        } catch (Exception e) {
            return "ERR:" + e.getClass().getSimpleName();
        }
        if (range == null) {
            return "null";
        }
        try {
            range.getMin();
        } catch (Exception e) {
            return "ERR:" + e.getClass().getSimpleName();
        }
        try {
            range.getMax();
        } catch (Exception e) {
            // Boundary case: non-null range, getMin ok, getMax out of bounds.
            return "min";
        }
        return "okMM";
    }

    static PDRange invokeGetDecodeForParameter(PDShading shading, int param) {
        if (shading instanceof PDShadingType4) {
            return ((PDShadingType4) shading).getDecodeForParameter(param);
        }
        if (shading instanceof PDShadingType5) {
            return ((PDShadingType5) shading).getDecodeForParameter(param);
        }
        if (shading instanceof PDShadingType6) {
            return ((PDShadingType6) shading).getDecodeForParameter(param);
        }
        if (shading instanceof PDShadingType7) {
            return ((PDShadingType7) shading).getDecodeForParameter(param);
        }
        return null;
    }

    static int bitsPerCoordinate(PDShading s) {
        if (s instanceof PDShadingType4) {
            return ((PDShadingType4) s).getBitsPerCoordinate();
        }
        if (s instanceof PDShadingType5) {
            return ((PDShadingType5) s).getBitsPerCoordinate();
        }
        if (s instanceof PDShadingType6) {
            return ((PDShadingType6) s).getBitsPerCoordinate();
        }
        if (s instanceof PDShadingType7) {
            return ((PDShadingType7) s).getBitsPerCoordinate();
        }
        return -99;
    }

    static int bitsPerComponent(PDShading s) {
        if (s instanceof PDShadingType4) {
            return ((PDShadingType4) s).getBitsPerComponent();
        }
        if (s instanceof PDShadingType5) {
            return ((PDShadingType5) s).getBitsPerComponent();
        }
        if (s instanceof PDShadingType6) {
            return ((PDShadingType6) s).getBitsPerComponent();
        }
        if (s instanceof PDShadingType7) {
            return ((PDShadingType7) s).getBitsPerComponent();
        }
        return -99;
    }

    /** /BitsPerFlag: Type4 exposes a typed accessor; Types 5/6/7 don't (Type5
     * has no flag at all). Project the raw COS int uniformly for parity with
     * pypdfbox's get_bits_per_flag on all four types. */
    static int bitsPerFlag(PDShading s) {
        return s.getCOSObject().getInt(BITS_PER_FLAG);
    }

    static String ncc(PDShading s) {
        try {
            int n;
            if (s instanceof PDShadingType4) {
                n = ((PDShadingType4) s).getNumberOfColorComponents();
            } else if (s instanceof PDShadingType5) {
                n = ((PDShadingType5) s).getNumberOfColorComponents();
            } else if (s instanceof PDShadingType6) {
                n = ((PDShadingType6) s).getNumberOfColorComponents();
            } else if (s instanceof PDShadingType7) {
                n = ((PDShadingType7) s).getNumberOfColorComponents();
            } else {
                return "n/a";
            }
            return Integer.toString(n);
        } catch (Exception e) {
            return "ERR:" + e.getClass().getSimpleName();
        }
    }

    static String funcProjection(PDShading shading) {
        try {
            PDFunction f = shading.getFunction();
            return f == null ? "null" : f.getClass().getSimpleName();
        } catch (Exception e) {
            return "ERR:" + e.getClass().getSimpleName();
        }
    }

    static String bboxProjection(PDShading shading) {
        try {
            PDRectangle r = shading.getBBox();
            return r == null ? "null" : "rect";
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
                sb.append("type=null class=null bpc=n/a bcomp=n/a bflag=n/a "
                        + "vpr=n/a ncc=n/a dec=null d0=null dc=null bg=null "
                        + "bbox=null aa=false function=null");
            } else {
                String t;
                try {
                    t = Integer.toString(shading.getShadingType());
                } catch (Exception e) {
                    t = "ERR";
                }
                String vpr;
                if (shading instanceof PDShadingType5) {
                    vpr = Integer.toString(
                            ((PDShadingType5) shading).getVerticesPerRow());
                } else {
                    vpr = "n/a";
                }
                COSArray dec =
                        shading.getCOSObject().getCOSArray(COSName.DECODE);
                COSArray bg = shading.getBackground();
                sb.append("type=").append(t);
                sb.append(" class=").append(shading.getClass().getSimpleName());
                sb.append(" bpc=").append(bitsPerCoordinate(shading));
                sb.append(" bcomp=").append(bitsPerComponent(shading));
                sb.append(" bflag=").append(bitsPerFlag(shading));
                sb.append(" vpr=").append(vpr);
                sb.append(" ncc=").append(ncc(shading));
                sb.append(" dec=").append(arrArity(dec));
                sb.append(" d0=").append(decodeParam(shading, 0));
                sb.append(" dc=").append(decodeParam(shading, 2));
                sb.append(" bg=").append(arrArity(bg));
                sb.append(" bbox=").append(bboxProjection(shading));
                sb.append(" aa=").append(shading.getAntiAlias());
                sb.append(" function=").append(funcProjection(shading));
            }
        } catch (Exception e) {
            sb.append("type=ERR class=ERR:")
                    .append(e.getClass().getSimpleName())
                    .append(" bpc=ERR bcomp=ERR bflag=ERR vpr=ERR ncc=ERR "
                            + "dec=ERR d0=ERR dc=ERR bg=ERR bbox=ERR aa=ERR "
                            + "function=ERR");
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
