import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.InputStream;
import java.io.PrintStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDDocumentCatalog;
import org.apache.pdfbox.pdmodel.PDResources;
import org.apache.pdfbox.pdmodel.interactive.form.PDAcroForm;
import org.apache.pdfbox.pdmodel.interactive.form.PDXFAResource;

/**
 * Differential fuzz probe for the AcroForm /XFA entry + top-level AcroForm dict
 * accessors, Apache PDFBox 3.0.7 (wave 1560, agent E).
 *
 * <p>Complements the existing well-formed AcroForm oracle suite
 * (AcroFormAccessorProbe, AcroFormDefaultFixupProbe, FieldTreeProbe,
 * AcroFormFieldFuzzProbe) — none of which exercise the MALFORMED /XFA payload
 * shapes a hostile / buggy producer can emit, nor the wrong-typed top-level
 * AcroForm accessors. This probe targets, per case:
 * <ul>
 *   <li>{@code /XFA} as a single stream vs a packet array
 *       ([name stream name stream]), with well-formed pairs, odd-length arrays,
 *       non-stream entries, name labels as COSName vs COSString;</li>
 *   <li>{@code /XFA} absent / wrong-type (dict / number / bool);</li>
 *   <li>{@code /DA} missing / string / name / number;</li>
 *   <li>{@code /DR} missing / dict / non-dict;</li>
 *   <li>{@code /NeedAppearances} bool / non-bool;</li>
 *   <li>{@code /SigFlags} int / non-int;</li>
 *   <li>{@code /CO} calculation-order array malformed / non-array;</li>
 *   <li>{@code /Fields} non-array / containing non-dict.</li>
 * </ul>
 *
 * <p>Driven file-based, mirroring AcroFormFieldFuzzProbe: the pypdfbox sibling
 * writes a deterministic corpus of hand-built PDFs into a directory plus a
 * {@code manifest.txt} (one case name per line, in order); this probe loads each
 * {@code <case>.pdf} via {@code Loader.loadPDF}, takes the AcroForm with NO fixup
 * ({@code getAcroForm(null)}) so the raw parse contract is observed, and projects
 * the form-level accessor surface. Both sides read the exact same bytes on disk.
 *
 * <p>Line grammar (UTF-8, LF-terminated). One CASE line per case in manifest
 * order:
 * <pre>
 *   CASE &lt;name&gt; form=&lt;present|absent|ERR:&lt;Exc&gt;&gt; hasxfa=&lt;b|?&gt; \
 *        xfa=&lt;present|absent|ERR&gt; xfalen=&lt;n|ERR|-&gt; da=&lt;text|ERR&gt; \
 *        dr=&lt;present|absent|ERR&gt; needapp=&lt;b|ERR&gt; sigflags=&lt;n|ERR&gt; \
 *        co=&lt;n|ERR&gt; nfields=&lt;n|ERR&gt;
 * </pre>
 */
public final class XfaAcroFormFuzzProbe {

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

    static String hasXfa(PDAcroForm form) {
        try {
            return Boolean.toString(form.hasXFA());
        } catch (Exception e) {
            return err(e);
        }
    }

    static String xfaPresent(PDAcroForm form) {
        try {
            return form.getXFA() != null ? "present" : "absent";
        } catch (Exception e) {
            return err(e);
        }
    }

    static String xfaLen(PDAcroForm form) {
        try {
            PDXFAResource xfa = form.getXFA();
            if (xfa == null) {
                return "-";
            }
            byte[] b = xfa.getBytes();
            return b == null ? "null" : Integer.toString(b.length);
        } catch (Exception e) {
            return err(e);
        }
    }

    static String da(PDAcroForm form) {
        try {
            return esc(form.getDefaultAppearance());
        } catch (Exception e) {
            return err(e);
        }
    }

    static String dr(PDAcroForm form) {
        try {
            PDResources r = form.getDefaultResources();
            return r != null ? "present" : "absent";
        } catch (Exception e) {
            return err(e);
        }
    }

    static String needApp(PDAcroForm form) {
        try {
            return Boolean.toString(form.getNeedAppearances());
        } catch (Exception e) {
            return err(e);
        }
    }

    static String sigFlags(PDAcroForm form) {
        try {
            return Integer.toString(
                    form.getCOSObject().getInt(COSName.getPDFName("SigFlags"), 0));
        } catch (Exception e) {
            return err(e);
        }
    }

    static String co(PDAcroForm form) {
        try {
            return Integer.toString(form.getCalcOrder().size());
        } catch (Exception e) {
            return err(e);
        }
    }

    static String nfields(PDAcroForm form) {
        try {
            return Integer.toString(form.getFields().size());
        } catch (Exception e) {
            return err(e);
        }
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
                out.println("CASE " + name + " form=" + err(e));
                return;
            }
            if (form == null) {
                out.println("CASE " + name + " form=absent");
                return;
            }
            StringBuilder sb = new StringBuilder("CASE ").append(name);
            sb.append(" form=present");
            sb.append(" hasxfa=").append(hasXfa(form));
            sb.append(" xfa=").append(xfaPresent(form));
            sb.append(" xfalen=").append(xfaLen(form));
            sb.append(" da=").append(da(form));
            sb.append(" dr=").append(dr(form));
            sb.append(" needapp=").append(needApp(form));
            sb.append(" sigflags=").append(sigFlags(form));
            sb.append(" co=").append(co(form));
            sb.append(" nfields=").append(nfields(form));
            out.println(sb.toString());
        } catch (Exception e) {
            out.println("CASE " + name + " form=ERR:" + e.getClass().getSimpleName());
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

    // Unused helper kept to mirror the byte-reading convention used elsewhere;
    // PDXFAResource.getBytes already concatenates, so we rely on it directly.
    static byte[] readAll(InputStream in) throws Exception {
        ByteArrayOutputStream bos = new ByteArrayOutputStream();
        byte[] buf = new byte[4096];
        int n;
        while ((n = in.read(buf)) != -1) {
            bos.write(buf, 0, n);
        }
        return bos.toByteArray();
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
