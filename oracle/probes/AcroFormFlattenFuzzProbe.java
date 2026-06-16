import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.PrintStream;
import java.util.ArrayList;
import java.util.List;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSStream;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDDocumentCatalog;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.interactive.form.PDAcroForm;
import org.apache.pdfbox.pdmodel.interactive.form.PDField;

/**
 * Differential fuzz probe for {@code PDAcroForm.flatten(...)}, Apache PDFBox
 * 3.0.7 (wave 1565, agent E).
 *
 * <p>The existing flatten oracle ({@code test_flatten_oracle.py} /
 * {@code FlattenProbe.java}) drives a handful of curated on-disk fixtures
 * through a flatten and compares per-page widget counts + content growth. This
 * probe complements it by fuzzing the flatten DECISION SURFACE across many
 * hand-built field configurations that exercise the branches inside
 * {@code flatten}:
 * <ul>
 *   <li>a text field carrying a value + a real {@code /AP /N} appearance;</li>
 *   <li>a text field with NO appearance flattened with
 *       {@code refreshAppearances=true} (upstream regenerates the AP) vs
 *       {@code =false} (no AP to bake);</li>
 *   <li>a check box flattened in its on-state vs its off-state (state dict +
 *       {@code /AS} selection);</li>
 *   <li>a SUBSET flatten ({@code flatten(List.of(one), false)}) leaving the
 *       other fields + the {@code /AcroForm} dict intact;</li>
 *   <li>an empty form (no fields) — flatten is a no-op;</li>
 *   <li>a field whose single widget lives on page 2 (multi-page
 *       page-resolution via {@code /P});</li>
 *   <li>a non-terminal parent with two terminal kid widgets;</li>
 *   <li>a hidden ({@code /F} bit 2) widget — removed from {@code /Annots} but
 *       not drawn;</li>
 *   <li>a widget with no {@code /P} back-pointer (reverse-walk page lookup).</li>
 * </ul>
 *
 * <p>Driven file-based, mirroring {@code AcroFormFieldFuzzProbe}: the pypdfbox
 * sibling test writes a deterministic corpus of hand-built PDFs into a directory
 * plus a {@code manifest.txt} where each line is
 * {@code <case>\t<op>\t<arg>} — {@code op} is one of {@code all} (flatten
 * everything, refreshAppearances=false), {@code all-refresh} (flatten
 * everything, refreshAppearances=true), {@code subset} (flatten only the field
 * named by {@code arg}, refreshAppearances=false), or {@code subset-refresh}.
 * Both sides read the EXACT same bytes on disk, run the same flatten op, then
 * project a STABLE shape (counts + presence flags, never raw bytes) so the
 * observable flatten contract is directly comparable.
 *
 * <p>Per case the probe emits, LF-terminated, UTF-8:
 * <pre>
 *   CASE &lt;name&gt; preFields=&lt;n&gt; preWidgets=&lt;n&gt; pages=&lt;n&gt;
 *   FLAT &lt;name&gt; op=&lt;op&gt; result=&lt;ok|ERR:&lt;Exc&gt;&gt; acroform=&lt;0/1&gt; \
 *        postFields=&lt;n&gt; postWidgets=&lt;n&gt; valueBaked=&lt;0/1&gt; grew=&lt;0/1&gt;
 *   ENDCASE &lt;name&gt;
 * </pre>
 * where {@code postWidgets} is the total {@code /Subtype /Widget} count summed
 * across every page after flatten + save + reload, {@code valueBaked} is 1 when
 * the marker token {@code FLATMARK} appears anywhere in any page's decoded
 * content or registered Form-XObject bodies, and {@code grew} is 1 when the
 * summed page content length increased relative to pre-flatten. Counts are read
 * from a RELOAD of the saved bytes so the comparison reflects the persisted
 * outcome, not the in-memory object graph.
 */
public final class AcroFormFlattenFuzzProbe {

    static final COSName WIDGET = COSName.getPDFName("Widget");
    static PrintStream out;

    static int countWidgets(PDDocument doc) {
        int total = 0;
        for (PDPage page : doc.getPages()) {
            COSBase annots = page.getCOSObject().getDictionaryObject(COSName.ANNOTS);
            if (!(annots instanceof COSArray)) {
                continue;
            }
            COSArray arr = (COSArray) annots;
            for (int i = 0; i < arr.size(); i++) {
                COSBase entry = arr.getObject(i);
                if (entry instanceof COSDictionary) {
                    COSBase sub = ((COSDictionary) entry).getDictionaryObject(COSName.SUBTYPE);
                    if (WIDGET.equals(sub)) {
                        total++;
                    }
                }
            }
        }
        return total;
    }

    static int rootFields(PDDocument doc) {
        PDAcroForm form = doc.getDocumentCatalog().getAcroForm();
        if (form == null) {
            return 0;
        }
        COSBase fields = form.getCOSObject().getDictionaryObject(COSName.FIELDS);
        return (fields instanceof COSArray) ? ((COSArray) fields).size() : 0;
    }

    static long contentLength(PDDocument doc) throws Exception {
        long total = 0;
        for (PDPage page : doc.getPages()) {
            COSBase contents = page.getCOSObject().getDictionaryObject(COSName.CONTENTS);
            if (contents instanceof COSStream) {
                total += streamLen((COSStream) contents);
            } else if (contents instanceof COSArray) {
                COSArray arr = (COSArray) contents;
                for (int i = 0; i < arr.size(); i++) {
                    COSBase entry = arr.getObject(i);
                    if (entry instanceof COSStream) {
                        total += streamLen((COSStream) entry);
                    }
                }
            }
        }
        return total;
    }

    static long streamLen(COSStream stream) throws Exception {
        long len = 0;
        try (var in = stream.createInputStream()) {
            byte[] buf = new byte[8192];
            int n;
            while ((n = in.read(buf)) != -1) {
                len += n;
            }
        }
        return len;
    }

    /** True when FLATMARK appears in any page content stream OR any page
     *  /Resources /XObject Form body — the baked field value marker. */
    static boolean valueBaked(PDDocument doc) throws Exception {
        byte[] needle = "FLATMARK".getBytes("ISO-8859-1");
        for (PDPage page : doc.getPages()) {
            COSDictionary pd = page.getCOSObject();
            COSBase contents = pd.getDictionaryObject(COSName.CONTENTS);
            if (contains(collect(contents), needle)) {
                return true;
            }
            COSBase res = pd.getDictionaryObject(COSName.RESOURCES);
            if (res instanceof COSDictionary) {
                COSBase xobj = ((COSDictionary) res).getDictionaryObject(COSName.XOBJECT);
                if (xobj instanceof COSDictionary) {
                    COSDictionary xd = (COSDictionary) xobj;
                    for (COSName key : xd.keySet()) {
                        COSBase entry = xd.getDictionaryObject(key);
                        if (entry instanceof COSStream
                                && contains(streamBytes((COSStream) entry), needle)) {
                            return true;
                        }
                    }
                }
            }
        }
        return false;
    }

    static List<byte[]> collect(COSBase contents) throws Exception {
        List<byte[]> blobs = new ArrayList<>();
        if (contents instanceof COSStream) {
            blobs.add(streamBytes((COSStream) contents));
        } else if (contents instanceof COSArray) {
            COSArray arr = (COSArray) contents;
            for (int i = 0; i < arr.size(); i++) {
                COSBase entry = arr.getObject(i);
                if (entry instanceof COSStream) {
                    blobs.add(streamBytes((COSStream) entry));
                }
            }
        }
        return blobs;
    }

    static byte[] streamBytes(COSStream stream) throws Exception {
        ByteArrayOutputStream bos = new ByteArrayOutputStream();
        try (var in = stream.createInputStream()) {
            byte[] buf = new byte[8192];
            int n;
            while ((n = in.read(buf)) != -1) {
                bos.write(buf, 0, n);
            }
        }
        return bos.toByteArray();
    }

    static boolean contains(byte[] hay, byte[] needle) {
        if (hay.length < needle.length) {
            return false;
        }
        for (int i = 0; i <= hay.length - needle.length; i++) {
            boolean hit = true;
            for (int j = 0; j < needle.length; j++) {
                if (hay[i + j] != needle[j]) {
                    hit = false;
                    break;
                }
            }
            if (hit) {
                return true;
            }
        }
        return false;
    }

    static boolean contains(List<byte[]> blobs, byte[] needle) {
        for (byte[] b : blobs) {
            if (contains(b, needle)) {
                return true;
            }
        }
        return false;
    }

    static String err(Throwable t) {
        return "ERR:" + t.getClass().getSimpleName();
    }

    static void runCase(File dir, String name, String op, String arg) {
        File pdf = new File(dir, name + ".pdf");
        int preFields = 0;
        int preWidgets = 0;
        int pages = 0;
        long preLen = 0;

        try (PDDocument pre = Loader.loadPDF(pdf)) {
            preFields = rootFields(pre);
            preWidgets = countWidgets(pre);
            pages = pre.getNumberOfPages();
            preLen = contentLength(pre);
        } catch (Exception e) {
            out.println("CASE " + name + " preFields=? preWidgets=? pages=?");
            out.println("FLAT " + name + " op=" + op + " result=" + err(e)
                    + " acroform=? postFields=? postWidgets=? valueBaked=? grew=?");
            out.println("ENDCASE " + name);
            return;
        }

        out.println("CASE " + name + " preFields=" + preFields
                + " preWidgets=" + preWidgets + " pages=" + pages);

        byte[] saved;
        try {
            saved = flattenAndSave(pdf, op, arg);
        } catch (Exception e) {
            out.println("FLAT " + name + " op=" + op + " result=" + err(e)
                    + " acroform=? postFields=? postWidgets=? valueBaked=? grew=?");
            out.println("ENDCASE " + name);
            return;
        }

        try (PDDocument post = Loader.loadPDF(saved)) {
            boolean hasForm = post.getDocumentCatalog().getAcroForm() != null;
            int postFields = rootFields(post);
            int postWidgets = countWidgets(post);
            boolean baked = valueBaked(post);
            long postLen = contentLength(post);
            out.println("FLAT " + name + " op=" + op + " result=ok"
                    + " acroform=" + (hasForm ? "1" : "0")
                    + " postFields=" + postFields
                    + " postWidgets=" + postWidgets
                    + " valueBaked=" + (baked ? "1" : "0")
                    + " grew=" + (postLen > preLen ? "1" : "0"));
        } catch (Exception e) {
            out.println("FLAT " + name + " op=" + op + " result=" + err(e)
                    + " acroform=? postFields=? postWidgets=? valueBaked=? grew=?");
        }
        out.println("ENDCASE " + name);
    }

    static byte[] flattenAndSave(File pdf, String op, String arg) throws Exception {
        try (PDDocument doc = Loader.loadPDF(pdf)) {
            PDDocumentCatalog catalog = doc.getDocumentCatalog();
            PDAcroForm form = catalog.getAcroForm();
            if (form == null) {
                ByteArrayOutputStream bos = new ByteArrayOutputStream();
                doc.save(bos);
                return bos.toByteArray();
            }
            boolean refresh = op.endsWith("refresh");
            if (op.startsWith("subset")) {
                List<PDField> only = new ArrayList<>();
                PDField field = form.getField(arg);
                if (field != null) {
                    only.add(field);
                }
                form.flatten(only, refresh);
            } else {
                if (refresh) {
                    form.flatten(form.getFieldTree() == null ? new ArrayList<>()
                            : toList(form), true);
                } else {
                    form.flatten();
                }
            }
            ByteArrayOutputStream bos = new ByteArrayOutputStream();
            doc.save(bos);
            return bos.toByteArray();
        }
    }

    static List<PDField> toList(PDAcroForm form) {
        List<PDField> all = new ArrayList<>();
        for (PDField f : form.getFieldTree()) {
            if (f.getParent() == null) {
                all.add(f);
            }
        }
        return all;
    }

    public static void main(String[] args) throws Exception {
        out = new PrintStream(System.out, true, "UTF-8");
        File dir = new File(args[0]);
        File manifest = new File(dir, "manifest.txt");
        String[] lines =
                new String(java.nio.file.Files.readAllBytes(manifest.toPath()),
                                java.nio.charset.StandardCharsets.UTF_8)
                        .split("\n");
        for (String raw : lines) {
            String line = raw.trim();
            if (line.isEmpty()) {
                continue;
            }
            String[] parts = line.split("\t", -1);
            String name = parts[0];
            String op = parts.length > 1 ? parts[1] : "all";
            String arg = parts.length > 2 ? parts[2] : "";
            runCase(dir, name, op, arg);
        }
    }
}
