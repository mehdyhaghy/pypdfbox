import java.io.File;
import java.io.PrintStream;
import java.util.ArrayList;
import java.util.List;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDDocumentCatalog;
import org.apache.pdfbox.pdmodel.interactive.form.PDAcroForm;
import org.apache.pdfbox.pdmodel.interactive.form.PDButton;
import org.apache.pdfbox.pdmodel.interactive.form.PDChoice;
import org.apache.pdfbox.pdmodel.interactive.form.PDField;

/**
 * Differential fuzz probe for AcroForm FIELD-dict parsing + value/option
 * coercion leniency, Apache PDFBox 3.0.7 (wave 1513, agent B).
 *
 * <p>Complements the existing well-formed AcroForm oracle suite
 * (FieldProbe, ChoiceFieldProbe, FieldFlagsProbe, FieldSetProbe,
 * FieldQualifiedValueProbe, AcroFormDefaultFixupProbe) — none of which exercise
 * the MALFORMED field-dictionary subset a buggy / hostile producer can emit.
 * This probe targets, per field:
 * <ul>
 *   <li>{@code /FT} missing / unknown / inherited-from-parent;</li>
 *   <li>{@code /V} and {@code /DV} as string vs name vs array vs number vs
 *       missing vs wrong-type for the field type;</li>
 *   <li>{@code /Opt} as array of strings vs [export, display] pairs vs a bare
 *       string vs malformed (nested non-string, ragged pairs);</li>
 *   <li>{@code /Ff} flag bits (Radio, Pushbutton, Combo, Edit, MultiSelect,
 *       RadiosInUnison, …) including conflicting / out-of-range values;</li>
 *   <li>{@code /Q} quadding, {@code /MaxLen}, {@code /I} (selected indices)
 *       out of range / wrong-type;</li>
 *   <li>widget-vs-field merged single dictionaries;</li>
 *   <li>{@code /Kids} terminal-vs-nonterminal ambiguity.</li>
 * </ul>
 *
 * <p>Driven file-based: the pypdfbox sibling
 * (tests/pdmodel/interactive/form/oracle/test_acroform_field_fuzz_wave1513.py)
 * writes a deterministic corpus of hand-built single-field-dict PDFs into a
 * directory plus a {@code manifest.txt} (one case name per line, in order);
 * this probe loads each {@code <case>.pdf} via {@code Loader.loadPDF}, takes the
 * AcroForm with NO fixup ({@code getAcroForm(null)}) so the raw parse contract
 * is observed (the no-arg {@code getAcroForm()} would apply AcroFormDefaultFixup
 * and mutate /DA, /DR and orphan-adopt widgets), and walks the field tree. Both
 * sides read the exact same bytes on disk so the contract is directly
 * comparable.
 *
 * <p>Line grammar (UTF-8, LF-terminated). One CASE header then zero-or-more
 * FIELD lines, then a CASE-END line, per case in manifest order:
 * <pre>
 *   CASE &lt;name&gt; form=&lt;present|absent|ERR:&lt;Exc&gt;&gt; nfields=&lt;n-or-?&gt;
 *   FIELD &lt;fqn&gt; type=&lt;Class&gt; ft=&lt;FT|?&gt; value=&lt;text|ERR:&lt;Exc&gt;&gt; \
 *         default=&lt;text|ERR:&lt;Exc&gt;&gt; options=&lt;[..]|ERR:&lt;Exc&gt;|-&gt; \
 *         indices=&lt;[..]|ERR:&lt;Exc&gt;|-&gt; flags=&lt;n|ERR:&lt;Exc&gt;&gt;
 *   ENDCASE &lt;name&gt;
 * </pre>
 *
 * <p>{@code value} is {@code getValueAsString()}; {@code default} is the typed
 * default value (string for text/button, {@code Arrays.toString} of the list for
 * choice); {@code options} is {@code getOptions()} for a choice and
 * {@code getExportValues()} for a button else {@code -}; {@code indices} is
 * {@code getSelectedOptionsIndex()} for a choice else {@code -}; {@code flags}
 * is {@code getFieldFlags()}. Any accessor that throws is rendered
 * {@code ERR:<ExcSimpleName>} so a divergence in throw-vs-return is visible.
 * Newlines / tabs / spaces inside text values are escaped so each record stays
 * single-line; field order within a case is by tree-walk (deterministic for the
 * single-field corpus).
 */
public final class AcroFormFieldFuzzProbe {

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

    static String list(List<?> xs) {
        StringBuilder sb = new StringBuilder("[");
        for (int i = 0; i < xs.size(); i++) {
            if (i > 0) {
                sb.append(",");
            }
            sb.append(esc(String.valueOf(xs.get(i))));
        }
        return sb.append("]").toString();
    }

    static String fieldType(PDField f) {
        try {
            String t = f.getFieldType();
            return t == null ? "?" : t;
        } catch (Exception e) {
            return err(e);
        }
    }

    static String value(PDField f) {
        try {
            // A signature field's getValueAsString() returns the PDSignature
            // object's toString() — a non-portable identity/summary string that
            // both libraries render differently (Java object@hash vs the
            // pypdfbox repr). Collapse it to a stable present/absent token so the
            // comparison stays on the behavioural contract (is a /V dict
            // present?) rather than the incomparable object render.
            if (f instanceof org.apache.pdfbox.pdmodel.interactive.form.PDSignatureField) {
                Object sig = ((org.apache.pdfbox.pdmodel.interactive.form.PDSignatureField) f)
                        .getValue();
                return sig != null ? "<sig-present>" : "<sig-absent>";
            }
            return esc(f.getValueAsString());
        } catch (Exception e) {
            return err(e);
        }
    }

    static String defaultValue(PDField f) {
        try {
            if (f instanceof PDChoice) {
                return list(((PDChoice) f).getDefaultValue());
            }
            if (f instanceof PDButton) {
                return esc(((PDButton) f).getDefaultValue());
            }
            if (f instanceof org.apache.pdfbox.pdmodel.interactive.form.PDTextField) {
                return esc(((org.apache.pdfbox.pdmodel.interactive.form.PDTextField) f)
                        .getDefaultValue());
            }
            return "-";
        } catch (Exception e) {
            return err(e);
        }
    }

    static String options(PDField f) {
        try {
            if (f instanceof PDChoice) {
                return list(((PDChoice) f).getOptions());
            }
            if (f instanceof PDButton) {
                return list(((PDButton) f).getExportValues());
            }
            return "-";
        } catch (Exception e) {
            return err(e);
        }
    }

    static String indices(PDField f) {
        try {
            if (f instanceof PDChoice) {
                return list(((PDChoice) f).getSelectedOptionsIndex());
            }
            return "-";
        } catch (Exception e) {
            return err(e);
        }
    }

    static String flags(PDField f) {
        try {
            return Integer.toString(f.getFieldFlags());
        } catch (Exception e) {
            return err(e);
        }
    }

    static void emitField(PDField f) {
        StringBuilder sb = new StringBuilder("FIELD ");
        String fqn;
        try {
            fqn = f.getFullyQualifiedName();
        } catch (Exception e) {
            fqn = err(e);
        }
        sb.append(esc(fqn));
        sb.append(" type=").append(f.getClass().getSimpleName());
        sb.append(" ft=").append(fieldType(f));
        sb.append(" value=").append(value(f));
        sb.append(" default=").append(defaultValue(f));
        sb.append(" options=").append(options(f));
        sb.append(" indices=").append(indices(f));
        sb.append(" flags=").append(flags(f));
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
