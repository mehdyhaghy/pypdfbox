import java.io.File;
import java.io.PrintStream;
import java.util.ArrayList;
import java.util.List;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDDocumentCatalog;
import org.apache.pdfbox.pdmodel.interactive.form.PDAcroForm;
import org.apache.pdfbox.pdmodel.interactive.form.PDButton;
import org.apache.pdfbox.pdmodel.interactive.form.PDCheckBox;
import org.apache.pdfbox.pdmodel.interactive.form.PDChoice;
import org.apache.pdfbox.pdmodel.interactive.form.PDComboBox;
import org.apache.pdfbox.pdmodel.interactive.form.PDField;
import org.apache.pdfbox.pdmodel.interactive.form.PDListBox;
import org.apache.pdfbox.pdmodel.interactive.form.PDPushButton;
import org.apache.pdfbox.pdmodel.interactive.form.PDRadioButton;
import org.apache.pdfbox.pdmodel.interactive.form.PDTerminalField;
import org.apache.pdfbox.pdmodel.interactive.form.PDTextField;

/**
 * Differential fuzz probe for the PDField VALUE + FLAG-PREDICATE + NAME surface,
 * Apache PDFBox 3.0.7 (wave 1542, agent A).
 *
 * <p>Complements the existing AcroForm field oracle suite. None of those probes
 * exercise the TYPED FLAG-PREDICATE METHODS as predicates — they read only the
 * raw {@code getFieldFlags()} int (FieldFlagsProbe / AcroFormFieldFuzzProbe) or
 * the value/default/options projection (AcroFormFieldFuzzProbe). This probe
 * isolates, per field:
 * <ul>
 *   <li>the resolved field-type class chosen by the factory + {@code getFieldType()};</li>
 *   <li>{@code isTerminal()} (PDTerminalField vs PDNonTerminalField);</li>
 *   <li>the base flag predicates {@code isReadOnly / isRequired / isNoExport};</li>
 *   <li>text predicates {@code isMultiline / isPassword / isComb / isFileSelect /
 *       doNotScroll / doNotSpellCheck / isRichText};</li>
 *   <li>button predicates {@code isPushButton / isRadioButton} plus radio
 *       {@code isRadiosInUnison};</li>
 *   <li>choice predicates {@code isCombo / isEdit / isMultiSelect / isSort /
 *       isDoNotSpellCheck / isCommitOnSelChange};</li>
 *   <li>{@code getValue()} (the TYPED accessor: String for text/button,
 *       List for choice) DISTINCT from {@code getValueAsString()};</li>
 *   <li>{@code getDefaultValue()} typed;</li>
 *   <li>{@code getFullyQualifiedName()} across pathological /T chains
 *       (missing-/T parent, dotted /T, empty /T, deep nesting).</li>
 * </ul>
 *
 * <p>Driven file-based like AcroFormFieldFuzzProbe: the pypdfbox sibling writes a
 * deterministic corpus of hand-built PDFs plus a {@code manifest.txt}. Both sides
 * take the AcroForm with NO fixup ({@code getAcroForm(null)}) so the raw parse
 * contract is observed, and walk the field tree. Output grammar (UTF-8,
 * LF-terminated):
 * <pre>
 *   CASE &lt;name&gt; form=&lt;present|absent|ERR:&lt;Exc&gt;&gt; nfields=&lt;n-or-?&gt;
 *   FIELD &lt;fqn&gt; type=&lt;Class&gt; ft=&lt;FT|?&gt; terminal=&lt;0/1&gt; \
 *         ro=&lt;0/1&gt; req=&lt;0/1&gt; nox=&lt;0/1&gt; preds=&lt;k:v,..|-&gt; \
 *         val=&lt;typed|ERR&gt; vas=&lt;str|ERR&gt; dv=&lt;typed|ERR&gt;
 *   ENDCASE &lt;name&gt;
 * </pre>
 *
 * <p>{@code preds} is the type-specific predicate matrix (a comma-joined
 * {@code key:0/1} list) or {@code -} when the field type has no extra predicates.
 * {@code val} is the typed {@code getValue()} (text/button String, choice list
 * rendered like {@code Arrays.toString}); {@code vas} is
 * {@code getValueAsString()}; {@code dv} is the typed {@code getDefaultValue()}.
 * Any accessor that throws is rendered {@code ERR:<ExcSimpleName>}.
 */
public final class FieldValueFuzzProbe {

    static PrintStream out;

    static String esc(String s) {
        if (s == null) {
            return "null";
        }
        return s.replace("\\", "\\\\").replace("\n", "\\n").replace("\r", "\\r")
                .replace("\t", "\\t").replace(" ", "\\s");
    }

    static String err(Throwable t) {
        return "ERR:" + t.getClass().getSimpleName();
    }

    static String b(boolean v) {
        return v ? "1" : "0";
    }

    static String list(List<?> xs) {
        StringBuilder sb = new StringBuilder("[");
        for (int i = 0; i < xs.size(); i++) {
            if (i > 0) {
                sb.append(", ");
            }
            sb.append(xs.get(i));
        }
        return esc(sb.append("]").toString());
    }

    static String fieldType(PDField f) {
        try {
            String t = f.getFieldType();
            return t == null ? "?" : t;
        } catch (Exception e) {
            return err(e);
        }
    }

    static String fqn(PDField f) {
        try {
            String n = f.getFullyQualifiedName();
            return n == null ? "null" : (n.isEmpty() ? "<empty>" : esc(n));
        } catch (Exception e) {
            return err(e);
        }
    }

    static String preds(PDField f) {
        try {
            if (f instanceof PDTextField) {
                PDTextField t = (PDTextField) f;
                return "multiline:" + b(t.isMultiline())
                        + ",password:" + b(t.isPassword())
                        + ",comb:" + b(t.isComb())
                        + ",fileSelect:" + b(t.isFileSelect())
                        + ",doNotScroll:" + b(t.doNotScroll())
                        + ",doNotSpellCheck:" + b(t.doNotSpellCheck())
                        + ",richText:" + b(t.isRichText());
            }
            if (f instanceof PDRadioButton) {
                PDRadioButton r = (PDRadioButton) f;
                return "push:" + b(r.isPushButton())
                        + ",radio:" + b(r.isRadioButton())
                        + ",unison:" + b(r.isRadiosInUnison());
            }
            if (f instanceof PDPushButton) {
                PDPushButton p = (PDPushButton) f;
                return "push:" + b(p.isPushButton())
                        + ",radio:" + b(p.isRadioButton());
            }
            if (f instanceof PDCheckBox) {
                PDCheckBox cb = (PDCheckBox) f;
                return "push:" + b(cb.isPushButton())
                        + ",radio:" + b(cb.isRadioButton());
            }
            if (f instanceof PDComboBox) {
                PDComboBox cmb = (PDComboBox) f;
                return "combo:" + b(cmb.isCombo())
                        + ",edit:" + b(cmb.isEdit())
                        + ",multiSelect:" + b(cmb.isMultiSelect())
                        + ",sort:" + b(cmb.isSort())
                        + ",doNotSpellCheck:" + b(cmb.isDoNotSpellCheck())
                        + ",commit:" + b(cmb.isCommitOnSelChange());
            }
            if (f instanceof PDListBox) {
                PDListBox lb = (PDListBox) f;
                return "combo:" + b(lb.isCombo())
                        + ",multiSelect:" + b(lb.isMultiSelect())
                        + ",sort:" + b(lb.isSort())
                        + ",doNotSpellCheck:" + b(lb.isDoNotSpellCheck())
                        + ",commit:" + b(lb.isCommitOnSelChange());
            }
            return "-";
        } catch (Exception e) {
            return err(e);
        }
    }

    static String typedValue(PDField f) {
        try {
            if (f instanceof PDChoice) {
                return list(((PDChoice) f).getValue());
            }
            if (f instanceof PDTextField) {
                return esc(((PDTextField) f).getValue());
            }
            if (f instanceof PDButton) {
                return esc(((PDButton) f).getValue());
            }
            return "-";
        } catch (Exception e) {
            return err(e);
        }
    }

    static String valueAsString(PDField f) {
        try {
            return esc(f.getValueAsString());
        } catch (Exception e) {
            return err(e);
        }
    }

    static String typedDefault(PDField f) {
        try {
            if (f instanceof PDChoice) {
                return list(((PDChoice) f).getDefaultValue());
            }
            if (f instanceof PDTextField) {
                return esc(((PDTextField) f).getDefaultValue());
            }
            if (f instanceof PDButton) {
                return esc(((PDButton) f).getDefaultValue());
            }
            return "-";
        } catch (Exception e) {
            return err(e);
        }
    }

    static void emitField(PDField f) {
        StringBuilder sb = new StringBuilder("FIELD ");
        sb.append(fqn(f));
        sb.append(" type=").append(f.getClass().getSimpleName());
        sb.append(" ft=").append(fieldType(f));
        sb.append(" terminal=").append(b(f instanceof PDTerminalField));
        boolean ro;
        boolean req;
        boolean nox;
        try {
            ro = f.isReadOnly();
            req = f.isRequired();
            nox = f.isNoExport();
            sb.append(" ro=").append(b(ro)).append(" req=").append(b(req))
                    .append(" nox=").append(b(nox));
        } catch (Exception e) {
            sb.append(" ro=").append(err(e)).append(" req=?").append(" nox=?");
        }
        sb.append(" preds=").append(preds(f));
        sb.append(" val=").append(typedValue(f));
        sb.append(" vas=").append(valueAsString(f));
        sb.append(" dv=").append(typedDefault(f));
        out.println(sb.toString());
    }

    static void runCase(File dir, String name) {
        File pdf = new File(dir, name + ".pdf");
        PDDocument doc = null;
        try {
            doc = Loader.loadPDF(pdf);
            PDDocumentCatalog catalog = doc.getDocumentCatalog();
            PDAcroForm form;
            try {
                form = catalog.getAcroForm(null);
            } catch (Exception e) {
                out.println("CASE " + name + " form=" + err(e) + " nfields=?");
                out.println("ENDCASE " + name);
                return;
            }
            if (form == null) {
                out.println("CASE " + name + " form=absent nfields=0");
                out.println("ENDCASE " + name);
                return;
            }
            List<PDField> fields = new ArrayList<>();
            String nfields;
            try {
                for (PDField f : form.getFieldTree()) {
                    fields.add(f);
                }
                nfields = Integer.toString(fields.size());
            } catch (Exception e) {
                out.println("CASE " + name + " form=present nfields=" + err(e));
                out.println("ENDCASE " + name);
                return;
            }
            out.println("CASE " + name + " form=present nfields=" + nfields);
            for (PDField f : fields) {
                emitField(f);
            }
            out.println("ENDCASE " + name);
        } catch (Exception e) {
            out.println("CASE " + name + " form=ERR:" + e.getClass().getSimpleName()
                    + " nfields=?");
            out.println("ENDCASE " + name);
        } finally {
            if (doc != null) {
                try {
                    doc.close();
                } catch (Exception ignored) {
                    // best-effort close
                }
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
        for (String raw : names) {
            String nm = raw.trim();
            if (!nm.isEmpty()) {
                runCase(dir, nm);
            }
        }
    }
}
