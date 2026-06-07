import java.io.File;
import java.io.PrintStream;
import java.util.Arrays;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.PDResources;
import org.apache.pdfbox.pdmodel.graphics.PDFontSetting;
import org.apache.pdfbox.pdmodel.graphics.PDLineDashPattern;
import org.apache.pdfbox.pdmodel.graphics.blend.BlendMode;
import org.apache.pdfbox.pdmodel.graphics.state.PDExtendedGraphicsState;
import org.apache.pdfbox.pdmodel.graphics.state.PDSoftMask;
import org.apache.pdfbox.pdmodel.graphics.state.RenderingIntent;

/**
 * Differential fuzz probe for {@link PDExtendedGraphicsState} accessor leniency
 * over a MALFORMED {@code /ExtGState} graphics-state parameter dictionary,
 * Apache PDFBox 3.0.7 (wave 1514, agent A).
 *
 * <p>Complements the well-formed ExtGState parity suites (round-trip getters,
 * copyIntoGraphicsState application) — none of which exercise the malformed /
 * wrong-type subset this probe targets:
 * <ul>
 *   <li>{@code /CA} {@code /ca} alpha as number / out-of-range / wrong type /
 *       missing</li>
 *   <li>{@code /BM} blend mode as name / array / unknown / missing</li>
 *   <li>{@code /LW} line width, {@code /LC} line cap, {@code /LJ} line join,
 *       {@code /ML} miter limit — wrong type / missing</li>
 *   <li>{@code /D} dash array {@code [dashArray phase]} malformed (wrong arity,
 *       non-numeric, empty)</li>
 *   <li>{@code /Font} {@code [font size]} array malformed</li>
 *   <li>{@code /SMask} as name {@code /None} / dict / bad</li>
 *   <li>{@code /AIS} {@code /TK} {@code /SA} {@code /OP} {@code /op} {@code /OPM}
 *       booleans/ints wrong type</li>
 *   <li>{@code /FL} flatness, {@code /SM} smoothness, {@code /RI} rendering
 *       intent name / unknown / wrong type</li>
 *   <li>{@code /TR} {@code /TR2} transfer (array arity != 4 filtered)</li>
 * </ul>
 *
 * <p>Driven file-based: the pypdfbox sibling
 * (tests/pdmodel/graphics/state/oracle/test_extgstate_fuzz_wave1514.py) writes
 * the deterministic corpus of one-page PDFs (each carrying the mutated ExtGState
 * dict as resource {@code /ExtGState/GS1}) plus a {@code manifest.txt} (one case
 * name per line, in order) into a tmp directory. This probe loads each
 * {@code <case>.pdf}, resolves the first page resources, fetches the state via
 * {@link PDResources#getExtGState}, and projects the accessor contract. Both
 * sides read the exact same bytes on disk, so the accessor leniency is directly
 * comparable.
 *
 * <p>Line grammar (one per case, manifest order):
 * <pre>
 *   CASE &lt;name&gt; lw=&lt;f|null&gt; lc=&lt;int&gt; lj=&lt;int&gt; ml=&lt;f|null&gt; \
 *       ca=&lt;f|null&gt; cana=&lt;f|null&gt; bm=&lt;name&gt; ais=&lt;0|1&gt; \
 *       tk=&lt;0|1&gt; sa=&lt;0|1&gt; op=&lt;0|1&gt; opns=&lt;0|1&gt; opm=&lt;int|null&gt; \
 *       fl=&lt;f|null&gt; sm=&lt;f|null&gt; ri=&lt;enum|null&gt; dash=&lt;arity|null&gt; \
 *       font=&lt;arity|null&gt; fontsize=&lt;f|null&gt; smask=&lt;kind&gt; \
 *       tr=&lt;arity|null&gt; tr2=&lt;arity|null&gt;
 * </pre>
 * where {@code f} is a number formatted via {@link #fmt}, {@code arity} is
 * {@code absent} / {@code arrN} / a COS class simple name, {@code bm} is the
 * resolved {@link BlendMode#getName}, {@code ri} is the typed
 * {@link RenderingIntent#name} (or {@code null} when {@code /RI} is absent), and
 * {@code smask} is {@code null} (absent or name {@code /None}) /
 * {@code dict:<SubType|null>} (a soft-mask dictionary) / {@code ERR}.
 *
 * <p>Any accessor that throws is reported as the field value {@code ERR}; an
 * outright {@code getExtGState} failure or a null state yields an all-ERR /
 * all-null line so the two sides still align row-for-row.
 */
public final class ExtGStateFuzzProbe {

    static PrintStream out;

    static String fmt(Float f) {
        if (f == null) {
            return "null";
        }
        float v = f;
        if (Float.isNaN(v)) {
            return "nan";
        }
        if (v == Math.rint(v) && !Float.isInfinite(v)) {
            return Integer.toString((int) v);
        }
        return Float.toString(v);
    }

    static String arity(COSBase base) {
        if (base == null) {
            return "absent";
        }
        if (base instanceof COSArray) {
            return "arr" + ((COSArray) base).size();
        }
        return base.getClass().getSimpleName();
    }

    static String dashProj(PDExtendedGraphicsState gs) {
        try {
            PDLineDashPattern d = gs.getLineDashPattern();
            if (d == null) {
                return "null";
            }
            // Project to the resolved dash-array length + phase so a
            // round-tripped pattern is comparable across both ports.
            return "dash" + d.getDashArray().length + ":" + fmt((float) d.getPhase());
        } catch (Exception e) {
            return "ERR";
        }
    }

    static String fontProj(PDExtendedGraphicsState gs) {
        try {
            PDFontSetting fs = gs.getFontSetting();
            if (fs == null) {
                return "null";
            }
            return "set";
        } catch (Exception e) {
            return "ERR";
        }
    }

    static String fontSizeProj(PDExtendedGraphicsState gs) {
        try {
            PDFontSetting fs = gs.getFontSetting();
            if (fs == null) {
                return "null";
            }
            return fmt((float) fs.getFontSize());
        } catch (Exception e) {
            return "ERR";
        }
    }

    static String smaskProj(PDExtendedGraphicsState gs) {
        try {
            PDSoftMask sm = gs.getSoftMask();
            if (sm == null) {
                return "null";
            }
            COSName st = sm.getSubType();
            return "dict:" + (st == null ? "null" : st.getName());
        } catch (Exception e) {
            return "ERR";
        }
    }

    static String bmProj(PDExtendedGraphicsState gs) {
        try {
            BlendMode bm = gs.getBlendMode();
            if (bm == null) {
                return "null";
            }
            COSName cn = bm.getCOSName();
            return cn == null ? "null" : cn.getName();
        } catch (Exception e) {
            return "ERR";
        }
    }

    static String riProj(PDExtendedGraphicsState gs) {
        try {
            RenderingIntent ri = gs.getRenderingIntent();
            return ri == null ? "null" : ri.name();
        } catch (Exception e) {
            return "ERR";
        }
    }

    interface FloatGetter {
        Float get();
    }

    static String f(FloatGetter g) {
        try {
            return fmt(g.get());
        } catch (Exception e) {
            return "ERR";
        }
    }

    interface IntGetter {
        int get();
    }

    static String i(IntGetter g) {
        try {
            return Integer.toString(g.get());
        } catch (Exception e) {
            return "ERR";
        }
    }

    interface BoolGetter {
        boolean get();
    }

    static String b(BoolGetter g) {
        try {
            return g.get() ? "1" : "0";
        } catch (Exception e) {
            return "ERR";
        }
    }

    static String opmProj(PDExtendedGraphicsState gs) {
        try {
            Integer om = gs.getOverprintMode();
            return om == null ? "null" : Integer.toString(om);
        } catch (Exception e) {
            return "ERR";
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
            PDExtendedGraphicsState gs = res.getExtGState(COSName.getPDFName("GS1"));
            if (gs == null) {
                sb.append("STATE=null");
            } else {
                projectState(sb, gs);
            }
        } catch (Exception e) {
            sb.append("STATE=ERR:").append(e.getClass().getSimpleName());
        } finally {
            close(doc);
        }
        out.println(sb.toString());
    }

    static void projectState(StringBuilder sb, PDExtendedGraphicsState gs) {
        sb.append("lw=").append(f(gs::getLineWidth));
        sb.append(" lc=").append(i(gs::getLineCapStyle));
        sb.append(" lj=").append(i(gs::getLineJoinStyle));
        sb.append(" ml=").append(f(gs::getMiterLimit));
        sb.append(" ca=").append(f(gs::getStrokingAlphaConstant));
        sb.append(" cana=").append(f(gs::getNonStrokingAlphaConstant));
        sb.append(" bm=").append(bmProj(gs));
        sb.append(" ais=").append(b(gs::getAlphaSourceFlag));
        sb.append(" tk=").append(b(gs::getTextKnockoutFlag));
        sb.append(" sa=").append(b(gs::getAutomaticStrokeAdjustment));
        sb.append(" op=").append(b(gs::getStrokingOverprintControl));
        sb.append(" opns=").append(b(gs::getNonStrokingOverprintControl));
        sb.append(" opm=").append(opmProj(gs));
        sb.append(" fl=").append(f(gs::getFlatnessTolerance));
        sb.append(" sm=").append(f(gs::getSmoothnessTolerance));
        sb.append(" ri=").append(riProj(gs));
        sb.append(" dash=").append(dashProj(gs));
        sb.append(" font=").append(fontProj(gs));
        sb.append(" fontsize=").append(fontSizeProj(gs));
        sb.append(" smask=").append(smaskProj(gs));
        sb.append(" tr=").append(transferProj(gs, false));
        sb.append(" tr2=").append(transferProj(gs, true));
    }

    static String transferProj(PDExtendedGraphicsState gs, boolean two) {
        try {
            COSBase base = two ? gs.getTransfer2() : gs.getTransfer();
            return arity(base);
        } catch (Exception e) {
            return "ERR";
        }
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
