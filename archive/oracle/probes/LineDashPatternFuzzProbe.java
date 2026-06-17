import java.io.PrintStream;
import java.util.Arrays;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBoolean;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSNull;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.pdmodel.graphics.PDLineDashPattern;

/**
 * Differential fuzz probe for {@link PDLineDashPattern} over a MALFORMED dash
 * array + phase, Apache PDFBox 3.0.7 (wave 1531, agent B).
 *
 * <p>The upstream class surface is tiny: the two constructors
 * ({@code PDLineDashPattern()} and {@code PDLineDashPattern(COSArray, int)}),
 * {@link PDLineDashPattern#getDashArray} (a {@code float[]}),
 * {@link PDLineDashPattern#getPhase} (an {@code int}), and
 * {@link PDLineDashPattern#getCOSObject} (the outer {@code [dashArray phase]}
 * array). The {@code phase} field is stored as an {@code int}; the constructor
 * normalises a negative phase by repeatedly adding twice the sum of the dash
 * lengths (truncating to int at the end). {@code getDashArray} delegates to
 * {@link COSArray#toFloatArray}, which yields one slot per element and maps any
 * non-{@code COSNumber} element to {@code 0.0f} (it does NOT drop the element).
 *
 * <p>This probe reads a {@code manifest.txt} of one case per line:
 * <pre>
 *   &lt;name&gt;|&lt;elem&gt;,&lt;elem&gt;,...|&lt;phase&gt;
 * </pre>
 * where each {@code elem} encodes one dash-array entry to materialise into a
 * {@link COSArray}, and {@code phase} is an integer (upstream's constructor only
 * accepts an {@code int} phase). The dash-element spelling:
 * <ul>
 *   <li>{@code i<n>} → {@link COSInteger}</li>
 *   <li>{@code f<v>} → {@link COSFloat}</li>
 *   <li>{@code name} → a {@link COSName} (non-numeric)</li>
 *   <li>{@code str} → a {@link COSString} (non-numeric)</li>
 *   <li>{@code bool} → {@link COSBoolean#TRUE} (non-numeric)</li>
 *   <li>{@code null} → {@link COSNull} (non-numeric)</li>
 *   <li>{@code arr} → a nested empty {@link COSArray} (non-numeric)</li>
 * </ul>
 * An empty element list ({@code -}) yields an empty dash array.
 *
 * <p>Output (one line per case, manifest order):
 * <pre>
 *   CASE &lt;name&gt; arr=[v0,v1,...] phase=&lt;int|ERR&gt; cos=[[...],&lt;cosphase&gt;]
 * </pre>
 * {@code arr} is the {@code getDashArray()} projection (each float via
 * {@link #fmt}); {@code phase} is {@code getPhase()}; {@code cos} re-reads the
 * {@code getCOSObject()} round-trip — inner float array + the phase entry's COS
 * class + value — so the serialised form is comparable across both ports.
 */
public final class LineDashPatternFuzzProbe {

    static PrintStream out;

    static String fmt(float v) {
        if (Float.isNaN(v)) {
            return "nan";
        }
        if (Float.isInfinite(v)) {
            return v > 0 ? "inf" : "-inf";
        }
        if (v == Math.rint(v) && Math.abs(v) < 1e15) {
            return Long.toString((long) v);
        }
        return Float.toString(v);
    }

    static COSArray buildDashArray(String spec) {
        COSArray arr = new COSArray();
        if (spec.equals("-")) {
            return arr;
        }
        for (String elem : spec.split(",")) {
            arr.add(buildElem(elem.trim()));
        }
        return arr;
    }

    static org.apache.pdfbox.cos.COSBase buildElem(String elem) {
        if (elem.startsWith("i")) {
            return COSInteger.get(Long.parseLong(elem.substring(1)));
        }
        if (elem.startsWith("f")) {
            return new COSFloat(Float.parseFloat(elem.substring(1)));
        }
        switch (elem) {
            case "name":
                return COSName.getPDFName("X");
            case "str":
                return new COSString("s");
            case "bool":
                return COSBoolean.TRUE;
            case "null":
                return COSNull.NULL;
            case "arr":
                return new COSArray();
            default:
                throw new IllegalArgumentException("bad elem: " + elem);
        }
    }

    static String cosPhaseProj(COSArray cos) {
        org.apache.pdfbox.cos.COSBase phaseEntry = cos.getObject(1);
        if (phaseEntry instanceof COSInteger) {
            return "int:" + ((COSInteger) phaseEntry).longValue();
        }
        if (phaseEntry instanceof COSFloat) {
            return "float:" + fmt(((COSFloat) phaseEntry).floatValue());
        }
        return phaseEntry == null ? "null" : phaseEntry.getClass().getSimpleName();
    }

    static void runCase(String line) {
        String[] parts = line.split("\\|", -1);
        String name = parts[0];
        String spec = parts[1];
        int phaseIn = Integer.parseInt(parts[2]);
        StringBuilder sb = new StringBuilder();
        sb.append("CASE ").append(name).append(' ');
        try {
            COSArray dash = buildDashArray(spec);
            PDLineDashPattern p = new PDLineDashPattern(dash, phaseIn);
            float[] arr = p.getDashArray();
            StringBuilder ab = new StringBuilder("[");
            for (int i = 0; i < arr.length; i++) {
                if (i > 0) {
                    ab.append(',');
                }
                ab.append(fmt(arr[i]));
            }
            ab.append(']');
            sb.append("arr=").append(ab);
            sb.append(" phase=").append(p.getPhase());
            COSArray cos = (COSArray) p.getCOSObject();
            COSArray inner = (COSArray) cos.getObject(0);
            float[] innerArr = inner.toFloatArray();
            StringBuilder ib = new StringBuilder("[");
            for (int i = 0; i < innerArr.length; i++) {
                if (i > 0) {
                    ib.append(',');
                }
                ib.append(fmt(innerArr[i]));
            }
            ib.append(']');
            sb.append(" cos=[").append(ib).append(',').append(cosPhaseProj(cos)).append(']');
        } catch (Exception e) {
            sb.append("ERR:").append(e.getClass().getSimpleName());
        }
        out.println(sb.toString());
    }

    public static void main(String[] args) throws Exception {
        out = new PrintStream(System.out, true, "UTF-8");
        String manifest =
                new String(java.nio.file.Files.readAllBytes(new java.io.File(args[0]).toPath()),
                        java.nio.charset.StandardCharsets.UTF_8);
        Arrays.stream(manifest.split("\n"))
                .map(String::trim)
                .filter(s -> !s.isEmpty())
                .forEach(LineDashPatternFuzzProbe::runCase);
    }
}
