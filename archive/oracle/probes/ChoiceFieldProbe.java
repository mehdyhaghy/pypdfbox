import java.io.File;
import java.io.PrintStream;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.PDResources;
import org.apache.pdfbox.pdmodel.font.PDType1Font;
import org.apache.pdfbox.pdmodel.font.Standard14Fonts;
import org.apache.pdfbox.pdmodel.interactive.form.PDAcroForm;
import org.apache.pdfbox.pdmodel.interactive.form.PDComboBox;
import org.apache.pdfbox.pdmodel.interactive.form.PDListBox;

/**
 * Live oracle probe for AcroForm choice fields (PDListBox / PDComboBox).
 *
 * Builds an AcroForm carrying a multi-select list box with [export, display]
 * /Opt pairs and a (non-editable) combo box with flat string /Opt entries,
 * exercises getOptions / getOptionsExportValues / getOptionsDisplayValues,
 * single- and multi-value setValue, getValue, getValueAsString and
 * getSelectedOptionsIndex, then reloads the saved document and re-emits the
 * post-round-trip view. Every observable is rendered in a canonical,
 * repr-independent form so the pypdfbox side can compare exactly.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> ChoiceFieldProbe out.pdf
 *
 * Output (UTF-8, LF-terminated "key value" lines).
 */
public final class ChoiceFieldProbe {

    static String list(List<?> xs) {
        StringBuilder sb = new StringBuilder("[");
        for (int i = 0; i < xs.size(); i++) {
            if (i > 0) sb.append(", ");
            sb.append(String.valueOf(xs.get(i)));
        }
        return sb.append("]").toString();
    }

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        File output = new File(args[0]);

        try (PDDocument doc = new PDDocument()) {
            doc.addPage(new PDPage());
            PDAcroForm form = new PDAcroForm(doc);
            doc.getDocumentCatalog().setAcroForm(form);

            // /DA + /DR so appearance regeneration on setValue can run.
            PDResources dr = new PDResources();
            dr.put(org.apache.pdfbox.cos.COSName.getPDFName("Helv"),
                    new PDType1Font(Standard14Fonts.FontName.HELVETICA));
            form.setDefaultResources(dr);
            form.setDefaultAppearance("/Helv 0 Tf 0 g");
            // Skip appearance regeneration in applyChange(): isolate the test to
            // choice-field value/option semantics (no widgets attached here).
            form.setNeedAppearances(true);

            // ----- list box: multi-select, [export, display] /Opt pairs -----
            PDListBox lb = new PDListBox(form);
            lb.setPartialName("lb");
            lb.setMultiSelect(true);
            List<String> exports = Arrays.asList("e0", "e1", "e2", "e3");
            List<String> displays = Arrays.asList("Display Zero", "Display One",
                    "Display Two", "Display Three");
            lb.setOptions(exports, displays);

            out.print("lb_options " + list(lb.getOptions()) + "\n");
            out.print("lb_export " + list(lb.getOptionsExportValues()) + "\n");
            out.print("lb_display " + list(lb.getOptionsDisplayValues()) + "\n");

            // multi-value set: export values, out of /Opt order
            lb.setValue(Arrays.asList("e2", "e0"));
            out.print("lb_value " + list(lb.getValue()) + "\n");
            out.print("lb_value_str " + lb.getValueAsString() + "\n");
            out.print("lb_index " + list(lb.getSelectedOptionsIndex()) + "\n");

            form.getFields().add(lb);

            // ----- combo box: flat string /Opt entries -----
            PDComboBox cb = new PDComboBox(form);
            cb.setPartialName("cb");
            cb.setOptions(Arrays.asList("Alpha", "Beta", "Gamma"));
            out.print("cb_options " + list(cb.getOptions()) + "\n");

            cb.setValue("Beta");
            out.print("cb_value " + list(cb.getValue()) + "\n");
            out.print("cb_value_str " + cb.getValueAsString() + "\n");
            out.print("cb_index " + list(cb.getSelectedOptionsIndex()) + "\n");

            form.getFields().add(cb);

            doc.save(output);
        }

        // ----- reload and re-emit the persisted view -----
        try (PDDocument doc = Loader.loadPDF(output)) {
            PDAcroForm form = doc.getDocumentCatalog().getAcroForm();
            PDListBox lb = (PDListBox) form.getField("lb");
            PDComboBox cb = (PDComboBox) form.getField("cb");

            out.print("rt_lb_options " + list(lb.getOptions()) + "\n");
            out.print("rt_lb_display " + list(lb.getOptionsDisplayValues()) + "\n");
            out.print("rt_lb_value " + list(lb.getValue()) + "\n");
            out.print("rt_lb_index " + list(lb.getSelectedOptionsIndex()) + "\n");
            out.print("rt_cb_value " + list(cb.getValue()) + "\n");
            out.print("rt_cb_index " + list(cb.getSelectedOptionsIndex()) + "\n");

            // setValue(List) with a value NOT in /Opt should throw on a
            // non-editable combo (containsAll check). Emit the outcome.
            try {
                List<String> bad = new ArrayList<>();
                bad.add("NotAnOption");
                cb.setValue(bad);
                out.print("cb_bad_set ok\n");
            } catch (IllegalArgumentException e) {
                out.print("cb_bad_set IllegalArgumentException\n");
            }
        }
    }
}
