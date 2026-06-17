import java.io.PrintStream;
import java.util.Arrays;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSStream;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.interactive.form.PDAcroForm;
import org.apache.pdfbox.pdmodel.interactive.form.PDCheckBox;
import org.apache.pdfbox.pdmodel.interactive.form.PDRadioButton;

/**
 * Live oracle probe for {@link org.apache.pdfbox.pdmodel.interactive.form.PDButton}
 * strict checkValue + the empty-string membership in getOnValues for widgets
 * that lack an /AP normal-appearance dictionary.
 *
 * Builds the field shapes in memory (no fixture file needed) and emits one
 * labelled line per fact so the Python side can match exactly. Multi-valued
 * sets are joined with '|' in the field's own iteration order (LinkedHashSet
 * insertion order). An empty on-state name is rendered as the empty token, so
 * a set of {"", "Accepted"} prints as "|Accepted".
 */
public final class ButtonCheckValueProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");

        try (PDDocument doc = new PDDocument()) {
            PDAcroForm form = new PDAcroForm(doc);

            // ---- Case 1: checkbox with a single /AP /N on-state "Yes" ----
            PDCheckBox cb = new PDCheckBox(form);
            cb.getCOSObject().setItem(COSName.AP, normalAp("Yes"));
            out.println("cb_onvalues=" + join(cb.getOnValues()));
            out.println("cb_check_yes=" + tryCheck(cb, "Yes"));
            out.println("cb_check_off=" + tryCheck(cb, "Off"));
            out.println("cb_check_maybe=" + tryCheck(cb, "Maybe"));

            // ---- Case 2: button with kids, two with NO /AP, one "Accepted" ----
            PDCheckBox grp = new PDCheckBox(form);
            COSArray kids = new COSArray();
            kids.add(new COSDictionary());                 // widget, no /AP
            kids.add(widgetWithAp("Accepted"));            // widget with /AP
            kids.add(new COSDictionary());                 // widget, no /AP
            grp.getCOSObject().setItem(COSName.KIDS, kids);
            out.println("grp_onvalues=" + join(grp.getOnValues()));
            out.println("grp_check_accepted=" + tryCheck(grp, "Accepted"));
            out.println("grp_check_empty=" + tryCheck(grp, ""));
            out.println("grp_check_off=" + tryCheck(grp, "Off"));
            out.println("grp_check_nope=" + tryCheck(grp, "Nope"));

            // ---- Case 3: AP-less checkbox (fresh) -> onValues holds "" ----
            PDCheckBox bare = new PDCheckBox(form);
            COSArray bareKids = new COSArray();
            bareKids.add(new COSDictionary());
            bare.getCOSObject().setItem(COSName.KIDS, bareKids);
            out.println("bare_onvalues=" + join(bare.getOnValues()));
            out.println("bare_getonvalue=" + bare.getOnValue());
            out.println("bare_check_empty=" + tryCheck(bare, ""));
            out.println("bare_check_yes=" + tryCheck(bare, "Yes"));

            // ---- Case 4: /Opt export-values radio, dedup + order ----
            PDRadioButton rb = new PDRadioButton(form);
            rb.setExportValues(Arrays.asList("e1", "e2", "e1"));
            out.println("opt_onvalues=" + join(rb.getOnValues()));
            out.println("opt_check_e1=" + tryCheck(rb, "e1"));
            out.println("opt_check_e2=" + tryCheck(rb, "e2"));
            out.println("opt_check_off=" + tryCheck(rb, "Off"));
            out.println("opt_check_bad=" + tryCheck(rb, "zzz"));

            // ---- Case 5: setDefaultValue routes through strict checkValue ----
            PDCheckBox dv = new PDCheckBox(form);
            dv.getCOSObject().setItem(COSName.AP, normalAp("On"));
            out.println("dv_set_on=" + trySetDefault(dv, "On"));
            out.println("dv_set_bad=" + trySetDefault(dv, "Bad"));
        }
    }

    /**
     * A /AP dict with an /N subdict containing /Off and the given on-state.
     * The state entries are COSStreams (appearance streams): upstream's
     * PDAppearanceEntry.getSubDictionary() only surfaces keys whose value is a
     * COSStream, so plain COSDictionary placeholders are invisible to
     * getOnValueForWidget.
     */
    private static COSDictionary normalAp(String onState) {
        COSDictionary n = new COSDictionary();
        n.setItem(COSName.getPDFName(onState), new COSStream());
        n.setItem(COSName.Off, new COSStream());
        COSDictionary ap = new COSDictionary();
        ap.setItem(COSName.N, n);
        return ap;
    }

    /** A widget dictionary carrying a normal-appearance /AP /N on-state. */
    private static COSDictionary widgetWithAp(String onState) {
        COSDictionary w = new COSDictionary();
        w.setItem(COSName.AP, normalAp(onState));
        return w;
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

    /**
     * checkValue is package-private upstream and this probe lives in the
     * default package, so reach it via reflection. This isolates the strict
     * value-validation semantics from the appearance-mutation side effects of
     * the public setValue(String) (which would otherwise also throw for
     * unrelated reasons such as widgets.size() != options.size()).
     */
    private static String tryCheck(
            org.apache.pdfbox.pdmodel.interactive.form.PDButton b, String value)
            throws Exception {
        java.lang.reflect.Method m = org.apache.pdfbox.pdmodel.interactive.form.PDButton.class
                .getDeclaredMethod("checkValue", String.class);
        m.setAccessible(true);
        try {
            m.invoke(b, value);
            return "ok";
        } catch (java.lang.reflect.InvocationTargetException e) {
            if (e.getCause() instanceof IllegalArgumentException) {
                return "IllegalArgumentException";
            }
            throw e;
        }
    }

    private static String trySetDefault(
            org.apache.pdfbox.pdmodel.interactive.form.PDButton b, String value) {
        try {
            b.setDefaultValue(value);
            return "ok";
        } catch (IllegalArgumentException e) {
            return "IllegalArgumentException";
        }
    }
}
