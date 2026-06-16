import java.io.PrintStream;
import java.util.Arrays;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSStream;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationWidget;
import org.apache.pdfbox.pdmodel.interactive.form.PDAcroForm;
import org.apache.pdfbox.pdmodel.interactive.form.PDCheckBox;
import org.apache.pdfbox.pdmodel.interactive.form.PDRadioButton;

/**
 * Live oracle probe for BUTTON ON/OFF STATE RESOLUTION — wave 1549.
 *
 * Distinct from the existing button probes:
 *   - ButtonCheckValueProbe / ButtonOnValueFilterProbe pin checkValue strictness
 *     and the COSStream getSubDictionary filter for on-value discovery.
 *   - RadioGroupProbe drives a fixture-loaded radio group's selected export /
 *     index / unison facts.
 *
 * This probe instead pins how /AS, /V, check()/unCheck() and setValue() interact
 * to resolve the active appearance state of IN-MEMORY malformed/edge button
 * fields: /AS pointing at a non-existent /AP /N key, /V disagreeing with /AS,
 * the check()/unCheck()/isChecked round trip, getSelectedIndex when several
 * widgets are simultaneously non-Off, and the /Opt index path's resolved /AS.
 *
 * Each fact is one labelled "key=value" line. Multi-valued columns are '|'
 * joined; a null /AS renders as the literal token "null"; an empty string
 * renders as the empty token. Exceptions render as "IllegalArgumentException".
 */
public final class ButtonStateFuzzProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");

        try (PDDocument doc = new PDDocument()) {
            PDAcroForm form = new PDAcroForm(doc);

            // ---- Case 1: /AS points at a key absent from /AP /N ----
            // get_appearance_state echoes the raw /AS regardless of /N; isChecked
            // compares getValue() against getOnValue().
            PDCheckBox c1 = new PDCheckBox(form);
            c1.getCOSObject().setItem(COSName.AP, normalAp("Yes"));
            c1.getWidgets().get(0).setAppearanceState("Ghost");
            out.println("c1_as=" + as(c1));
            out.println("c1_onvalue=" + c1.getOnValue());
            out.println("c1_value=" + c1.getValue());
            out.println("c1_checked=" + b(c1.isChecked()));

            // ---- Case 2: /V is a name matching the on-state, /AS still stale ----
            // Directly poke /V (bypassing setValue) so /AS stays "Off"; getValue
            // reflects /V, isChecked compares to getOnValue.
            PDCheckBox c2 = new PDCheckBox(form);
            c2.getCOSObject().setItem(COSName.AP, normalAp("Yes"));
            c2.getWidgets().get(0).setAppearanceState("Off");
            c2.getCOSObject().setItem(COSName.V, COSName.getPDFName("Yes"));
            out.println("c2_value=" + c2.getValue());
            out.println("c2_as_before=" + as(c2));
            out.println("c2_checked=" + b(c2.isChecked()));
            // constructAppearances syncs /AS to /V when the key exists in /N.
            // Package-private upstream -> reach via reflection (this probe is in
            // the default package).
            constructAppearances(c2);
            out.println("c2_as_after=" + as(c2));

            // ---- Case 3: /V as COSString (not COSName) -> getValue() == "Off" ----
            PDCheckBox c3 = new PDCheckBox(form);
            c3.getCOSObject().setItem(COSName.AP, normalAp("Yes"));
            c3.getCOSObject().setItem(
                    COSName.V, new org.apache.pdfbox.cos.COSString("Yes"));
            out.println("c3_value=" + c3.getValue());
            out.println("c3_checked=" + b(c3.isChecked()));

            // ---- Case 4: check() then unCheck() round trip ----
            PDCheckBox c4 = new PDCheckBox(form);
            c4.getCOSObject().setItem(COSName.AP, normalAp("On"));
            c4.check();
            out.println("c4_after_check_value=" + c4.getValue());
            out.println("c4_after_check_as=" + as(c4));
            out.println("c4_after_check_checked=" + b(c4.isChecked()));
            c4.unCheck();
            out.println("c4_after_uncheck_value=" + c4.getValue());
            out.println("c4_after_uncheck_as=" + as(c4));
            out.println("c4_after_uncheck_checked=" + b(c4.isChecked()));

            // ---- Case 5: /AP /N has Off + two stream on-keys; getOnValue =
            //              FIRST non-Off (insertion order). setValue("Bbb"). ----
            PDCheckBox c5 = new PDCheckBox(form);
            COSDictionary n5 = new COSDictionary();
            n5.setItem(COSName.Off, new COSStream());
            n5.setItem(COSName.getPDFName("Aaa"), new COSStream());
            n5.setItem(COSName.getPDFName("Bbb"), new COSStream());
            COSDictionary ap5 = new COSDictionary();
            ap5.setItem(COSName.N, n5);
            c5.getCOSObject().setItem(COSName.AP, ap5);
            // getOnValues only surfaces the FIRST non-Off key per widget, so
            // "Bbb" is NOT an on-value even though it is a stream entry; setting
            // it would raise. Set the recognised first key "Aaa" instead, but
            // also pin that setting the second stream key "Bbb" is rejected.
            out.println("c5_onvalue=" + c5.getOnValue());
            out.println("c5_onvalues=" + join(c5.getOnValues()));
            out.println("c5_set_bbb=" + trySet(c5, "Bbb"));
            c5.setValue("Aaa");
            out.println("c5_value=" + c5.getValue());
            out.println("c5_as=" + as(c5));
            out.println("c5_checked=" + b(c5.isChecked()));

            // ---- Case 6: AP-less fresh checkbox: check() sets "" on-value ----
            PDCheckBox c6 = new PDCheckBox(form);
            out.println("c6_onvalue=" + c6.getOnValue());
            out.println("c6_value_before=" + c6.getValue());
            out.println("c6_checked_before=" + b(c6.isChecked()));
            c6.check();
            out.println("c6_value_after=" + c6.getValue());
            out.println("c6_as_after=" + as(c6));
            out.println("c6_checked_after=" + b(c6.isChecked()));

            // ---- Case 7: radio group, three kids; two widgets share on-state ----
            // colliding on-values; getSelectedIndex returns the FIRST non-Off.
            PDRadioButton r7 = new PDRadioButton(form);
            COSArray kids7 = new COSArray();
            kids7.add(widgetWithApAs("A", "Off"));
            kids7.add(widgetWithApAs("B", "B"));
            kids7.add(widgetWithApAs("A", "A"));
            r7.getCOSObject().setItem(COSName.KIDS, kids7);
            out.println("r7_onvalues=" + join(r7.getOnValues()));
            out.println("r7_widgeton=" + widgetOns(r7));
            out.println("r7_selectedindex=" + r7.getSelectedIndex());

            // ---- Case 8: radio with /Opt export values; setValue(int idx) ----
            // updateByValue installs the on-value of the widget at idx.
            PDRadioButton r8 = new PDRadioButton(form);
            COSArray kids8 = new COSArray();
            kids8.add(widgetWithAp("0"));
            kids8.add(widgetWithAp("1"));
            r8.getCOSObject().setItem(COSName.KIDS, kids8);
            r8.setExportValues(Arrays.asList("export0", "export1"));
            r8.setValue(1);
            out.println("r8_value=" + r8.getValue());
            out.println("r8_widgetas=" + widgetAs(r8));
            out.println("r8_selectedindex=" + r8.getSelectedIndex());
            out.println("r8_selectedexport=" + joinList(r8.getSelectedExportValues()));

            // ---- Case 9: radio setValue("Off") clears all widget /AS ----
            PDRadioButton r9 = new PDRadioButton(form);
            COSArray kids9 = new COSArray();
            kids9.add(widgetWithApAs("X", "X"));
            kids9.add(widgetWithApAs("Y", "Off"));
            r9.getCOSObject().setItem(COSName.KIDS, kids9);
            r9.setValue("Off");
            out.println("r9_value=" + r9.getValue());
            out.println("r9_widgetas=" + widgetAs(r9));
            out.println("r9_selectedindex=" + r9.getSelectedIndex());

            // ---- Case 10: RadiosInUnison flag toggling ----
            PDRadioButton r10 = new PDRadioButton(form);
            out.println("r10_unison_default=" + b(r10.isRadiosInUnison()));
            r10.setRadiosInUnison(true);
            out.println("r10_unison_set=" + b(r10.isRadiosInUnison()));
            out.println("r10_ff=" + r10.getFieldFlags());

            // ---- Case 11: setValue(name) with NO matching /AP key on any
            //              widget but the name IS an on-value: /AS -> Off,
            //              /V -> raw name. ----
            // Build via /Opt so checkValue accepts the name, but widgets carry a
            // DIFFERENT on-state so findMatchingAppearanceKey misses everywhere.
            PDRadioButton r11 = new PDRadioButton(form);
            COSArray kids11 = new COSArray();
            kids11.add(widgetWithAp("w0"));
            kids11.add(widgetWithAp("w1"));
            r11.getCOSObject().setItem(COSName.KIDS, kids11);
            r11.setExportValues(Arrays.asList("optA", "optB"));
            r11.setValue("optA");
            out.println("r11_value=" + r11.getValue());
            out.println("r11_widgetas=" + widgetAs(r11));
            out.println("r11_selectedindex=" + r11.getSelectedIndex());

            // ---- Case 12: setValue to a name not in onValues raises ----
            PDCheckBox c12 = new PDCheckBox(form);
            c12.getCOSObject().setItem(COSName.AP, normalAp("Yes"));
            out.println("c12_set_bad=" + trySet(c12, "Nope"));
            out.println("c12_set_yes=" + trySet(c12, "Yes"));
            out.println("c12_after_value=" + c12.getValue());
            out.println("c12_after_as=" + as(c12));
        }
    }

    // ---- builders ----

    private static COSDictionary normalAp(String onState) {
        COSDictionary n = new COSDictionary();
        n.setItem(COSName.getPDFName(onState), new COSStream());
        n.setItem(COSName.Off, new COSStream());
        COSDictionary ap = new COSDictionary();
        ap.setItem(COSName.N, n);
        return ap;
    }

    private static COSDictionary widgetWithAp(String onState) {
        COSDictionary w = new COSDictionary();
        w.setItem(COSName.AP, normalAp(onState));
        return w;
    }

    private static COSDictionary widgetWithApAs(String onState, String asState) {
        COSDictionary w = widgetWithAp(onState);
        w.setItem(COSName.AS, COSName.getPDFName(asState));
        return w;
    }

    // ---- emitters ----

    private static String as(org.apache.pdfbox.pdmodel.interactive.form.PDButton btn) {
        COSName asName = (COSName) btn.getWidgets().get(0).getCOSObject()
                .getDictionaryObject(COSName.AS);
        return asName == null ? "null" : asName.getName();
    }

    private static String widgetAs(PDRadioButton rb) {
        StringBuilder sb = new StringBuilder();
        boolean first = true;
        for (PDAnnotationWidget w : rb.getWidgets()) {
            if (!first) {
                sb.append('|');
            }
            COSName asName = (COSName) w.getCOSObject()
                    .getDictionaryObject(COSName.AS);
            sb.append(asName == null ? "null" : asName.getName());
            first = false;
        }
        return sb.toString();
    }

    private static String widgetOns(PDRadioButton rb) {
        StringBuilder sb = new StringBuilder();
        boolean first = true;
        for (PDAnnotationWidget w : rb.getWidgets()) {
            if (!first) {
                sb.append('|');
            }
            org.apache.pdfbox.pdmodel.interactive.annotation.PDAppearanceDictionary ap =
                    w.getAppearance();
            String on = "";
            if (ap != null && ap.getNormalAppearance() != null) {
                for (COSName key : ap.getNormalAppearance().getSubDictionary().keySet()) {
                    if (!COSName.Off.equals(key)) {
                        on = key.getName();
                        break;
                    }
                }
            }
            sb.append(on);
            first = false;
        }
        return sb.toString();
    }

    private static void constructAppearances(
            org.apache.pdfbox.pdmodel.interactive.form.PDButton b)
            throws Exception {
        java.lang.reflect.Method m =
                org.apache.pdfbox.pdmodel.interactive.form.PDButton.class
                        .getDeclaredMethod("constructAppearances");
        m.setAccessible(true);
        m.invoke(b);
    }

    private static String trySet(
            org.apache.pdfbox.pdmodel.interactive.form.PDButton b, String value)
            throws Exception {
        try {
            b.setValue(value);
            return "ok";
        } catch (IllegalArgumentException e) {
            return "IllegalArgumentException";
        }
    }

    private static String b(boolean v) {
        return v ? "1" : "0";
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

    private static String joinList(java.util.List<String> values) {
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < values.size(); i++) {
            if (i > 0) {
                sb.append('|');
            }
            sb.append(values.get(i));
        }
        return sb.toString();
    }
}
