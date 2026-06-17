import java.io.File;
import java.io.PrintStream;
import java.util.Arrays;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.PDResources;
import org.apache.pdfbox.pdmodel.graphics.color.PDColorSpace;
import org.apache.pdfbox.pdmodel.graphics.pattern.PDAbstractPattern;
import org.apache.pdfbox.pdmodel.graphics.shading.PDShading;

/**
 * Differential fuzz probe for {@link PDShading#create} (types 1 function-based,
 * 2 axial, 3 radial, 4-7 mesh) and {@link PDAbstractPattern#create} (tiling
 * type 1 / shading type 2) construction leniency, Apache PDFBox 3.0.7
 * (wave 1513, agent D).
 *
 * <p>Complements the well-formed shading/pattern parity suites (axial/radial
 * coord round-trips, mesh bit-depth decode, tiling-pattern resource walk) —
 * none of which exercise the MALFORMED dictionary subset this probe targets:
 * {@code /ShadingType} missing / unknown / out-of-range; {@code /ColorSpace}
 * missing / bad; {@code /Coords} wrong arity; {@code /Domain} / {@code /Extend}
 * / {@code /Function} / {@code /Background} / {@code /AntiAlias} malformed; mesh
 * {@code /BitsPerCoordinate} {@code /BitsPerComponent} {@code /BitsPerFlag}
 * {@code /Decode} corners; pattern {@code /PatternType} missing / unknown;
 * tiling {@code /PaintType} {@code /TilingType} {@code /BBox} {@code /XStep}
 * {@code /YStep} {@code /Resources} malformed; shading-pattern {@code /Shading}
 * + {@code /Matrix} bad.
 *
 * <p>Driven file-based: the pypdfbox sibling
 * (tests/pdmodel/graphics/shading/oracle/test_shading_pattern_fuzz_wave1513.py)
 * writes the deterministic corpus of one-page PDFs (each carrying the mutated
 * shading dict as resource {@code /Shading/Sh1} or the mutated pattern dict as
 * {@code /Pattern/P1}) plus a {@code manifest.txt} (one case name per line, in
 * order) into a tmp directory. This probe loads each {@code <case>.pdf},
 * resolves the first page resources, and invokes the matching factory through
 * {@link PDResources#getShading} / {@link PDResources#getPattern}. Both sides
 * read the exact same bytes on disk, so the construction contract is directly
 * comparable.
 *
 * <p>A case whose name begins {@code shading_} is projected through the shading
 * factory; {@code pattern_} through the pattern factory.
 *
 * <p>Line grammar (one per case, manifest order):
 * <pre>
 *   CASE &lt;name&gt; shadingType=&lt;n|ERR&gt; class=&lt;simpleName|null|ERR&gt; cs=&lt;name|ERR&gt; extra=&lt;key-projection|ERR&gt;
 * </pre>
 *
 * <p>For a shading case: {@code shadingType} = the resolved
 * {@code getShadingType()} (or ERR when the factory threw); {@code class} =
 * concrete simple class name (or null when the factory returned null);
 * {@code cs} = the color-space name resolved via {@code getColorSpace()} (or
 * "none" when absent, "ERR" when resolution threw); {@code extra} = a
 * type-specific key projection (Coords arity, Domain, Extend, Function presence,
 * AntiAlias, mesh bit depths).
 *
 * <p>For a pattern case: {@code shadingType} reuses the field to carry
 * {@code getPatternType()} (ERR on throw); {@code class} = concrete simple
 * class name; {@code cs} = "n/a"; {@code extra} = tiling paint/tiling-type/bbox
 * arity/xstep/ystep or shading-pattern nested shadingType + matrix arity.
 */
public final class ShadingPatternFuzzProbe {

    static PrintStream out;

    static String csName(PDShading shading) {
        try {
            PDColorSpace cs = shading.getColorSpace();
            return cs == null ? "none" : cs.getName();
        } catch (Exception e) {
            return "ERR";
        }
    }

    static String arity(COSBase base) {
        if (base == null) {
            return "absent";
        }
        if (base instanceof org.apache.pdfbox.cos.COSArray) {
            return "arr" + ((org.apache.pdfbox.cos.COSArray) base).size();
        }
        return base.getClass().getSimpleName();
    }

    static String shadingExtra(PDShading shading) {
        org.apache.pdfbox.cos.COSDictionary d = shading.getCOSObject();
        int t;
        try {
            t = shading.getShadingType();
        } catch (Exception e) {
            t = -1;
        }
        StringBuilder sb = new StringBuilder();
        if (t == 1) {
            sb.append("domain=").append(arity(d.getDictionaryObject(COSName.DOMAIN)));
            sb.append(",function=")
                    .append(d.getDictionaryObject(COSName.FUNCTION) == null ? "0" : "1");
        } else if (t == 2 || t == 3) {
            sb.append("coords=").append(arity(d.getDictionaryObject(COSName.COORDS)));
            sb.append(",domain=").append(arity(d.getDictionaryObject(COSName.DOMAIN)));
            sb.append(",extend=").append(arity(d.getDictionaryObject(COSName.EXTEND)));
            sb.append(",function=")
                    .append(d.getDictionaryObject(COSName.FUNCTION) == null ? "0" : "1");
        } else if (t >= 4 && t <= 7) {
            sb.append("bpcoord=").append(d.getInt(COSName.BITS_PER_COORDINATE, -1));
            sb.append(",bpcomp=").append(d.getInt(COSName.BITS_PER_COMPONENT, -1));
            sb.append(",bpflag=").append(d.getInt(COSName.BITS_PER_FLAG, -1));
            sb.append(",decode=").append(arity(d.getDictionaryObject(COSName.DECODE)));
        } else {
            sb.append("type=").append(t);
        }
        sb.append(",aa=").append(shading.getAntiAlias() ? "1" : "0");
        sb.append(",bg=").append(arity(d.getDictionaryObject(COSName.BACKGROUND)));
        return sb.toString();
    }

    static void runShadingCase(File dir, String name) {
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
                sb.append("shadingType=null class=null cs=null extra=null");
            } else {
                String st;
                try {
                    st = Integer.toString(shading.getShadingType());
                } catch (Exception e) {
                    st = "ERR";
                }
                sb.append("shadingType=").append(st);
                sb.append(" class=").append(shading.getClass().getSimpleName());
                sb.append(" cs=").append(csName(shading));
                sb.append(" extra=").append(shadingExtra(shading));
            }
        } catch (Exception e) {
            sb.append("shadingType=ERR class=ERR:")
                    .append(e.getClass().getSimpleName())
                    .append(" cs=ERR extra=ERR");
        } finally {
            close(doc);
        }
        out.println(sb.toString());
    }

    static String patternExtra(PDAbstractPattern pat) {
        org.apache.pdfbox.cos.COSDictionary d = pat.getCOSObject();
        int t;
        try {
            t = pat.getPatternType();
        } catch (Exception e) {
            t = -1;
        }
        StringBuilder sb = new StringBuilder();
        if (t == 1) {
            sb.append("paint=").append(d.getInt(COSName.PAINT_TYPE, -1));
            sb.append(",tiling=").append(d.getInt(COSName.TILING_TYPE, -1));
            sb.append(",bbox=").append(arity(d.getDictionaryObject(COSName.BBOX)));
            sb.append(",xstep=").append(fmt(d.getFloat(COSName.X_STEP, Float.NaN)));
            sb.append(",ystep=").append(fmt(d.getFloat(COSName.Y_STEP, Float.NaN)));
        } else if (t == 2) {
            COSBase shObj = d.getDictionaryObject(COSName.SHADING);
            String nested;
            try {
                org.apache.pdfbox.pdmodel.graphics.pattern.PDShadingPattern shp =
                        (org.apache.pdfbox.pdmodel.graphics.pattern.PDShadingPattern) pat;
                PDShading sh = shp.getShading();
                nested = sh == null ? "null"
                        : Integer.toString(sh.getShadingType());
            } catch (Exception e) {
                nested = "ERR:" + e.getClass().getSimpleName();
            }
            sb.append("shading=").append(shObj == null ? "absent" : "present");
            sb.append(",nestedType=").append(nested);
            sb.append(",matrix=").append(arity(d.getDictionaryObject(COSName.MATRIX)));
        } else {
            sb.append("type=").append(t);
        }
        return sb.toString();
    }

    static String fmt(float f) {
        if (Float.isNaN(f)) {
            return "nan";
        }
        if (f == Math.rint(f) && !Float.isInfinite(f)) {
            return Integer.toString((int) f);
        }
        return Float.toString(f);
    }

    static void runPatternCase(File dir, String name) {
        File pdf = new File(dir, name + ".pdf");
        StringBuilder sb = new StringBuilder();
        sb.append("CASE ").append(name).append(' ');
        PDDocument doc = null;
        try {
            doc = Loader.loadPDF(pdf);
            PDPage page = doc.getPage(0);
            PDResources res = page.getResources();
            PDAbstractPattern pat = res.getPattern(COSName.getPDFName("P1"));
            if (pat == null) {
                sb.append("shadingType=null class=null cs=n/a extra=null");
            } else {
                String pt;
                try {
                    pt = Integer.toString(pat.getPatternType());
                } catch (Exception e) {
                    pt = "ERR";
                }
                sb.append("shadingType=").append(pt);
                sb.append(" class=").append(pat.getClass().getSimpleName());
                sb.append(" cs=n/a");
                sb.append(" extra=").append(patternExtra(pat));
            }
        } catch (Exception e) {
            sb.append("shadingType=ERR class=ERR:")
                    .append(e.getClass().getSimpleName())
                    .append(" cs=ERR extra=ERR");
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

    static void runCase(File dir, String name) {
        if (name.startsWith("pattern_")) {
            runPatternCase(dir, name);
        } else {
            runShadingCase(dir, name);
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
