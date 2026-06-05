import java.io.PrintStream;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSStream;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.interactive.form.PDAcroForm;
import org.apache.pdfbox.pdmodel.interactive.form.PDCheckBox;

/**
 * Live oracle probe isolating the COSStream filter in PDButton on-value
 * discovery (wave 1488).
 *
 * Upstream {@code PDButton.getOnValueForWidget} and {@code PDCheckBox.getOnValue}
 * iterate {@code normalAppearance.getSubDictionary().keySet()}, and
 * {@code PDAppearanceEntry.getSubDictionary()} surfaces only keys whose VALUE is
 * a {@link COSStream}. A {@code /AP /N} state entry holding a non-stream
 * placeholder (a plain {@link COSDictionary} or a {@link COSName}) therefore
 * contributes NO on-value.
 *
 * The wave-1487 ButtonCheckValueProbe deliberately used COSStream on-states to
 * satisfy this filter; these cases instead build non-stream placeholders to
 * pin the filter itself. Each fact line is {@code key=value}; an empty
 * on-value renders as the empty token.
 */
public final class ButtonOnValueFilterProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");

        try (PDDocument doc = new PDDocument()) {
            PDAcroForm form = new PDAcroForm(doc);

            // ---- Case A: /N on-state is a COSStream (normal) ----
            PDCheckBox a = new PDCheckBox(form);
            a.getCOSObject().setItem(COSName.AP, ap(streamN("Yes")));
            out.println("a_onvalue=" + a.getOnValue());
            out.println("a_onvalues=" + join(a.getOnValues()));

            // ---- Case B: /N on-state is a plain COSDictionary placeholder ----
            PDCheckBox b = new PDCheckBox(form);
            COSDictionary bN = new COSDictionary();
            bN.setItem(COSName.getPDFName("Yes"), new COSDictionary());
            bN.setItem(COSName.Off, new COSStream());
            b.getCOSObject().setItem(COSName.AP, ap(bN));
            out.println("b_onvalue=" + b.getOnValue());
            out.println("b_onvalues=" + join(b.getOnValues()));

            // ---- Case C: /N on-state is a COSName placeholder ----
            PDCheckBox c = new PDCheckBox(form);
            COSDictionary cN = new COSDictionary();
            cN.setItem(COSName.getPDFName("Yes"), COSName.getPDFName("ref"));
            cN.setItem(COSName.Off, new COSStream());
            c.getCOSObject().setItem(COSName.AP, ap(cN));
            out.println("c_onvalue=" + c.getOnValue());
            out.println("c_onvalues=" + join(c.getOnValues()));

            // ---- Case D: /N mixes a non-stream key (first) + a stream key ----
            // Iteration order is insertion order; the non-stream "Aaa" must be
            // skipped and the stream-valued "Bbb" returned.
            PDCheckBox d = new PDCheckBox(form);
            COSDictionary dN = new COSDictionary();
            dN.setItem(COSName.getPDFName("Aaa"), new COSDictionary());
            dN.setItem(COSName.getPDFName("Bbb"), new COSStream());
            dN.setItem(COSName.Off, new COSStream());
            d.getCOSObject().setItem(COSName.AP, ap(dN));
            out.println("d_onvalue=" + d.getOnValue());
            out.println("d_onvalues=" + join(d.getOnValues()));

            // ---- Case E: /N has only non-stream placeholders -> no on-value ----
            PDCheckBox e = new PDCheckBox(form);
            COSDictionary eN = new COSDictionary();
            eN.setItem(COSName.getPDFName("Yes"), new COSDictionary());
            eN.setItem(COSName.Off, new COSDictionary());
            e.getCOSObject().setItem(COSName.AP, ap(eN));
            out.println("e_onvalue=" + e.getOnValue());
            out.println("e_onvalues=" + join(e.getOnValues()));
        }
    }

    private static COSDictionary streamN(String onState) {
        COSDictionary n = new COSDictionary();
        n.setItem(COSName.getPDFName(onState), new COSStream());
        n.setItem(COSName.Off, new COSStream());
        return n;
    }

    private static COSDictionary ap(COSDictionary n) {
        COSDictionary ap = new COSDictionary();
        ap.setItem(COSName.N, n);
        return ap;
    }

    private static String join(java.util.Set<String> values) {
        StringBuilder sb = new StringBuilder();
        boolean first = true;
        for (String v : values) {
            if (!first) {
                sb.append('|');
            }
            sb.append(v);
            first = false;
        }
        return sb.toString();
    }
}
