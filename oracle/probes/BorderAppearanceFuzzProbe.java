import java.io.File;
import java.io.PrintStream;
import java.util.Arrays;
import java.util.List;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.graphics.color.PDColor;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotation;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationWidget;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAppearanceCharacteristicsDictionary;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDBorderStyleDictionary;
import org.apache.pdfbox.pdmodel.graphics.PDLineDashPattern;

/**
 * Differential fuzz probe for the annotation border-style ({@code /BS}) and
 * appearance-characteristics ({@code /MK}) dictionaries, Apache PDFBox 3.0.7
 * (wave 1515, agent E).
 *
 * <p>Complements the well-formed border-style / MK oracle suites
 * ({@code BorderStyleProbe}, {@code BsAccessorProbe}, {@code WidgetIconProbe})
 * — none of which exercise the MALFORMED subset this probe targets:
 *
 * <ul>
 *   <li>{@code PDBorderStyleDictionary} {@code /BS}: {@code /W} width as a
 *       number / missing / negative / a real / a name / a string (Adobe quirk:
 *       a name {@code /W} reads as 0); {@code /S} style enum
 *       ({@code S}/{@code D}/{@code B}/{@code I}/{@code U}/unknown/missing/as a
 *       string → default {@code S}); {@code /D} dash array
 *       (well-formed / empty / non-numeric / missing / a single number / a name
 *       instead of an array);</li>
 *   <li>{@code PDAppearanceCharacteristicsDictionary} {@code /MK}: {@code /R}
 *       rotation (multiple of 90 / non-multiple / negative / a real / missing /
 *       a name); {@code /BC} border colour and {@code /BG} background colour
 *       arrays with 0/1/3/4 components (→ DeviceGray / DeviceRGB / DeviceCMYK,
 *       empty = no colour) and a wrong-type (name / number) entry;
 *       {@code /CA} normal caption (string / name / missing); the dict
 *       altogether missing.</li>
 * </ul>
 *
 * <p>Driven file-based: the pypdfbox sibling
 * (tests/pdmodel/interactive/annotation/oracle/test_border_appearance_fuzz_wave1515.py)
 * writes a deterministic corpus of one-page PDFs (each page carries a single
 * Widget annotation whose {@code /BS} and {@code /MK} sub-dicts are the mutated
 * dictionaries) plus a {@code manifest.txt} (one case name per line, in order)
 * into a tmp dir. This probe loads each {@code <case>.pdf}, resolves the first
 * page's first annotation as a {@link PDAnnotationWidget}, and projects a stable
 * framed line. Both sides read the exact same bytes on disk.
 *
 * <p>Line grammar (one per case, manifest order):
 *
 * <pre>
 *   CASE &lt;name&gt; bs_w=&lt;n|ERR:X&gt; bs_s=&lt;style|ERR:X&gt; bs_d=&lt;floats|none|ERR:X&gt; mk_r=&lt;n|ERR:X&gt; mk_bc=&lt;comp-count|none|ERR:X&gt; mk_bg=&lt;comp-count|none|ERR:X&gt; mk_ca=&lt;caption|none|ERR:X&gt;
 * </pre>
 *
 * <p>Where: {@code bs_w} = {@code PDBorderStyleDictionary.getWidth()};
 * {@code bs_s} = {@code getStyle()}; {@code bs_d} = the {@code /D} dash array as
 * a pipe-joined list of its float entries (via {@code getDashStyle()}), or
 * {@code none} when {@code /D} is absent / not an array; {@code mk_r} =
 * {@code PDAppearanceCharacteristicsDictionary.getRotation()}; {@code mk_bc} /
 * {@code mk_bg} = the component count of the typed {@code PDColor} returned by
 * {@code getBorderColour()} / {@code getBackground()} (or {@code none} when the
 * getter returns {@code null}); {@code mk_ca} = {@code getNormalCaption()} (or
 * {@code none}). "ERR:X" means the getter threw exception class X.
 */
public final class BorderAppearanceFuzzProbe {

    static PrintStream out;

    static String num(double d) {
        // Stable numeric rendering: integral doubles print without a trailing
        // ".0" so 1.0 and 1 compare equal across both libraries' projections.
        if (d == Math.rint(d) && !Double.isInfinite(d)) {
            return Long.toString((long) d);
        }
        return Double.toString(d);
    }

    static String bsWidth(PDBorderStyleDictionary bs) {
        try {
            return num(bs.getWidth());
        } catch (Exception e) {
            return "ERR:" + e.getClass().getSimpleName();
        }
    }

    static String bsStyle(PDBorderStyleDictionary bs) {
        try {
            String s = bs.getStyle();
            return s == null ? "none" : s;
        } catch (Exception e) {
            return "ERR:" + e.getClass().getSimpleName();
        }
    }

    static String bsDash(PDBorderStyleDictionary bs) {
        try {
            PDLineDashPattern d = bs.getDashStyle();
            if (d == null) {
                return "none";
            }
            float[] arr = d.getDashArray();
            if (arr == null || arr.length == 0) {
                return "empty";
            }
            StringBuilder sb = new StringBuilder();
            for (int i = 0; i < arr.length; i++) {
                if (i > 0) {
                    sb.append('|');
                }
                sb.append(num(arr[i]));
            }
            return sb.toString();
        } catch (Exception e) {
            return "ERR:" + e.getClass().getSimpleName();
        }
    }

    static String mkRotation(PDAppearanceCharacteristicsDictionary mk) {
        try {
            return Integer.toString(mk.getRotation());
        } catch (Exception e) {
            return "ERR:" + e.getClass().getSimpleName();
        }
    }

    static String mkColor(PDColor c) {
        if (c == null) {
            return "none";
        }
        float[] comps = c.getComponents();
        return Integer.toString(comps == null ? 0 : comps.length);
    }

    static String mkBorderColour(PDAppearanceCharacteristicsDictionary mk) {
        try {
            return mkColor(mk.getBorderColour());
        } catch (Exception e) {
            return "ERR:" + e.getClass().getSimpleName();
        }
    }

    static String mkBackground(PDAppearanceCharacteristicsDictionary mk) {
        try {
            return mkColor(mk.getBackground());
        } catch (Exception e) {
            return "ERR:" + e.getClass().getSimpleName();
        }
    }

    static String mkCaption(PDAppearanceCharacteristicsDictionary mk) {
        try {
            String s = mk.getNormalCaption();
            return s == null ? "none" : s;
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
            List<PDAnnotation> annots = page.getAnnotations();
            PDAnnotationWidget widget = (PDAnnotationWidget) annots.get(0);

            PDBorderStyleDictionary bs = widget.getBorderStyle();
            if (bs == null) {
                sb.append("bs_w=NOBS bs_s=NOBS bs_d=NOBS");
            } else {
                sb.append("bs_w=").append(bsWidth(bs));
                sb.append(" bs_s=").append(bsStyle(bs));
                sb.append(" bs_d=").append(bsDash(bs));
            }

            PDAppearanceCharacteristicsDictionary mk =
                    widget.getAppearanceCharacteristics();
            if (mk == null) {
                sb.append(" mk_r=NOMK mk_bc=NOMK mk_bg=NOMK mk_ca=NOMK");
            } else {
                sb.append(" mk_r=").append(mkRotation(mk));
                sb.append(" mk_bc=").append(mkBorderColour(mk));
                sb.append(" mk_bg=").append(mkBackground(mk));
                sb.append(" mk_ca=").append(mkCaption(mk));
            }
        } catch (Exception e) {
            sb.append("LOAD:").append(e.getClass().getSimpleName());
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
