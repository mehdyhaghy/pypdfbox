import java.io.ByteArrayInputStream;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Locale;
import org.apache.fontbox.afm.AFMParser;
import org.apache.fontbox.afm.CharMetric;
import org.apache.fontbox.afm.Composite;
import org.apache.fontbox.afm.CompositePart;
import org.apache.fontbox.afm.FontMetrics;
import org.apache.fontbox.afm.KernPair;
import org.apache.fontbox.afm.Ligature;
import org.apache.fontbox.afm.TrackKern;
import org.apache.fontbox.util.BoundingBox;

/**
 * Live oracle probe for the AFM parser under malformed input — wave 1548
 * differential font-metrics fuzz. Sibling of {@link AfmParserFuzzProbe}
 * (wave 1522) but projecting a DIFFERENT, richer slice of the parsed
 * {@link FontMetrics} so the two waves cover complementary surfaces:
 *
 *   - global vertical metrics (CapHeight / XHeight / Ascender / Descender /
 *     ItalicAngle / IsFixedPitch) which the wave-1522 fingerprint omitted;
 *   - the three kern-pair lists separately (KernPairs / KernPairs0 /
 *     KernPairs1) plus KPH hex pairs and StartTrackKern entries;
 *   - per-char extended width vectors (W / W0 / W1 / VV / WY) and L
 *     ligatures, which wave 1522 never reached.
 *
 * Reads raw (possibly corrupt) AFM bytes from a file, feeds them to FontBox's
 * {@link AFMParser} via {@code AFMParser(InputStream)} and {@code parse(reduced)}
 * (arg[1] = "0" full / "1" reduced), and prints a stable projection:
 *
 *   ok=true
 *   name=&lt;FontName or NULL&gt;
 *   vm=&lt;capHeight,xHeight,ascender,descender,italicAngle&gt; (4dp each)
 *   fixedpitch=&lt;true|false&gt;
 *   nchar=&lt;CharMetric count&gt;
 *   nkp=&lt;KernPairs size&gt;
 *   nkp0=&lt;KernPairs0 size&gt;
 *   nkp1=&lt;KernPairs1 size&gt;
 *   ntrack=&lt;TrackKern count&gt;
 *   ncomp=&lt;Composite count&gt;
 *   nlig=&lt;total ligatures across all CharMetrics&gt;
 *   cm0=&lt;name,code,wx,wy,w,w0,w1,vv,bbox of first CharMetric or NULL&gt;
 *   kp0=&lt;first,second,x,y of first KernPair sorted, or NULL&gt;
 *   tk0=&lt;degree,minPt,minKern,maxPt,maxKern of first TrackKern, or NULL&gt;
 *
 * or the sole line {@code ok=false} on any throw from {@code parse}. The
 * pypdfbox side reproduces this fingerprint exactly so the parity assertion is
 * a single string compare.
 *
 * Usage:
 *   java -cp ... AfmParseFuzzProbe font.afm [0|1]
 */
public final class AfmParseFuzzProbe {

    public static void main(String[] args) throws Exception {
        byte[] bytes = java.nio.file.Files.readAllBytes(
                new java.io.File(args[0]).toPath());
        boolean reduced = args.length > 1 && "1".equals(args[1]);

        StringBuilder sb = new StringBuilder();
        try {
            AFMParser parser = new AFMParser(new ByteArrayInputStream(bytes));
            FontMetrics fm = parser.parse(reduced);
            sb.append("ok=true\n");
            sb.append("name=").append(nz(fm.getFontName())).append('\n');
            sb.append("vm=")
                    .append(fmt(fm.getCapHeight())).append(',')
                    .append(fmt(fm.getXHeight())).append(',')
                    .append(fmt(fm.getAscender())).append(',')
                    .append(fmt(fm.getDescender())).append(',')
                    .append(fmt(fm.getItalicAngle())).append('\n');
            sb.append("fixedpitch=").append(fm.getIsFixedPitch()).append('\n');
            List<CharMetric> metrics = new ArrayList<>(fm.getCharMetrics());
            int nlig = 0;
            for (CharMetric cm : metrics) {
                List<Ligature> ligs = cm.getLigatures();
                if (ligs != null) {
                    nlig += ligs.size();
                }
            }
            List<TrackKern> tracks = new ArrayList<>(fm.getTrackKern());
            sb.append("nchar=").append(metrics.size()).append('\n');
            sb.append("nkp=").append(fm.getKernPairs().size()).append('\n');
            sb.append("nkp0=").append(fm.getKernPairs0().size()).append('\n');
            sb.append("nkp1=").append(fm.getKernPairs1().size()).append('\n');
            sb.append("ntrack=").append(tracks.size()).append('\n');
            sb.append("ncomp=").append(fm.getComposites().size()).append('\n');
            sb.append("nlig=").append(nlig).append('\n');
            sb.append("cm0=").append(cm0(metrics)).append('\n');
            sb.append("kp0=").append(kp0(fm.getKernPairs())).append('\n');
            sb.append("tk0=").append(tk0(tracks)).append('\n');
        } catch (Throwable t) {
            System.out.print("ok=false\n");
            return;
        }
        System.out.print(sb);
    }

    private static String cm0(List<CharMetric> metrics) {
        if (metrics.isEmpty()) {
            return "NULL";
        }
        metrics.sort(Comparator.comparing(m -> nz(m.getName())));
        CharMetric cm = metrics.get(0);
        return nz(cm.getName()) + "," + cm.getCharacterCode() + ","
                + fmt(cm.getWx()) + "," + fmt(cm.getWy()) + ","
                + pair(cm.getW()) + "," + pair(cm.getW0()) + ","
                + pair(cm.getW1()) + "," + pair(cm.getVv()) + ","
                + bboxStr(cm.getBoundingBox());
    }

    private static String kp0(List<KernPair> pairs) {
        if (pairs.isEmpty()) {
            return "NULL";
        }
        List<KernPair> copy = new ArrayList<>(pairs);
        copy.sort(Comparator
                .comparing((KernPair k) -> nz(k.getFirstKernCharacter()))
                .thenComparing(k -> nz(k.getSecondKernCharacter())));
        KernPair kp = copy.get(0);
        return nz(kp.getFirstKernCharacter()) + ","
                + nz(kp.getSecondKernCharacter()) + ","
                + fmt(kp.getX()) + "," + fmt(kp.getY());
    }

    private static String tk0(List<TrackKern> tracks) {
        if (tracks.isEmpty()) {
            return "NULL";
        }
        TrackKern tk = tracks.get(0);
        return tk.getDegree() + "," + fmt(tk.getMinPointSize()) + ","
                + fmt(tk.getMinKern()) + "," + fmt(tk.getMaxPointSize()) + ","
                + fmt(tk.getMaxKern());
    }

    private static String pair(float[] p) {
        if (p == null) {
            return "NULL";
        }
        return fmt(p[0]) + "/" + fmt(p[1]);
    }

    private static String bboxStr(BoundingBox b) {
        if (b == null) {
            return "NULL";
        }
        return fmt(b.getLowerLeftX()) + "," + fmt(b.getLowerLeftY()) + ","
                + fmt(b.getUpperRightX()) + "," + fmt(b.getUpperRightY());
    }

    private static String nz(String s) {
        return s == null ? "NULL" : s;
    }

    private static String fmt(float v) {
        if (v == 0.0f) {
            v = 0.0f;
        }
        return String.format(Locale.ROOT, "%.4f", v);
    }
}
