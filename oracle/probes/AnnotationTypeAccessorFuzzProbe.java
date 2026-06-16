import java.io.File;
import java.io.PrintStream;
import java.util.Arrays;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotation;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationFileAttachment;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationLink;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationMarkup;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationPopup;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationRubberStamp;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationText;

/**
 * Differential fuzz probe for the typed ACCESSORS of the less-common
 * annotation subtypes + the {@code PDAnnotation.createAnnotation} factory
 * dispatch, Apache PDFBox 3.0.7 (wave 1554, agent E).
 *
 * <p>Complements the existing annotation oracle suite. The geometry +
 * dispatch-class subset is already pinned by
 * {@code AnnotationDispatchFuzzProbe} (wave 1515) and the appearance-stream
 * generators by waves 1508/1509/1536/1544. NONE of those project the
 * per-type SCALAR accessors this probe targets:</p>
 * <ul>
 *   <li>factory: /Subtype known/unknown/missing/mistyped (a COSString instead
 *       of a COSName) -&gt; concrete class name.</li>
 *   <li>Link: getHighlightMode (/H name/string/missing/bogus), getQuadPoints
 *       arity, getDestination/getAction presence.</li>
 *   <li>Popup: getOpen (/Open bool/non-bool/missing), getParent typed cast
 *       (/Parent markup-dict / non-markup-dict / non-dict / fallback /P).</li>
 *   <li>Caret: getRectDifferences (/RD missing/short/long/non-numeric/non-array
 *       — note upstream returns float[0] when absent, never null).</li>
 *   <li>RubberStamp / FileAttachment / Text: icon /Name name/string/missing/
 *       bogus through getName / getAttachmentName (all read via
 *       getNameAsString, so a COSString resolves).</li>
 *   <li>Text: getState / getStateModel (/State, /StateModel string/name/missing
 *       — read via getString, so a COSName resolves to null).</li>
 * </ul>
 *
 * <p>Driven file-based, identical-bytes-on-disk (same pattern as the wave-1515
 * sibling): the pypdfbox test builds a deterministic corpus of annotation
 * dictionaries, embeds them as entries of a non-standard {@code /FuzzAnnots}
 * COSArray hung off the document catalog, and saves ONE {@code corpus.pdf} plus
 * a {@code manifest.txt} (one case name per line, in array order). This probe
 * loads that pdf, walks the array, feeds each raw COSDictionary to
 * {@code PDAnnotation.createAnnotation}, and projects one stable framed line per
 * case. Both sides read the same bytes, so the accessor contract is directly
 * comparable.</p>
 *
 * <p>Output grammar (one line per case, manifest order):</p>
 * <pre>
 *   CASE &lt;name&gt; class=&lt;simpleName|ERR:&lt;Exc&gt;&gt; acc=&lt;per-type projection&gt;
 * </pre>
 */
public final class AnnotationTypeAccessorFuzzProbe {

    static PrintStream out;

    private AnnotationTypeAccessorFuzzProbe() {
    }

    static String s(String v) {
        return v == null ? "null" : v;
    }

    static String qpProj(float[] a) {
        if (a == null) {
            return "null";
        }
        return "n" + a.length;
    }

    /** Per-subtype scalar-accessor projection. */
    static String accProj(PDAnnotation a) {
        try {
            if (a instanceof PDAnnotationLink) {
                PDAnnotationLink l = (PDAnnotationLink) a;
                return "H=" + s(l.getHighlightMode())
                        + " QP=" + qpProj(l.getQuadPoints())
                        + " act=" + (l.getAction() != null)
                        + " dst=" + (l.getDestination() != null);
            }
            if (a instanceof PDAnnotationPopup) {
                PDAnnotationPopup p = (PDAnnotationPopup) a;
                String parent;
                try {
                    PDAnnotationMarkup m = p.getParent();
                    parent = m == null ? "null" : m.getClass().getSimpleName();
                } catch (Exception e) {
                    parent = "ERR:" + e.getClass().getSimpleName();
                }
                return "open=" + p.getOpen() + " parent=" + parent;
            }
            if (a instanceof PDAnnotationText) {
                PDAnnotationText t = (PDAnnotationText) a;
                return "name=" + s(t.getName())
                        + " open=" + t.getOpen()
                        + " state=" + s(t.getState())
                        + " sm=" + s(t.getStateModel());
            }
            if (a instanceof PDAnnotationFileAttachment) {
                PDAnnotationFileAttachment f = (PDAnnotationFileAttachment) a;
                return "name=" + s(f.getAttachmentName())
                        + " file=" + (f.getFile() != null);
            }
            if (a instanceof PDAnnotationRubberStamp) {
                PDAnnotationRubberStamp r = (PDAnnotationRubberStamp) a;
                return "name=" + s(r.getName());
            }
            // Caret is read as a markup; project its /RD via the typed accessor.
            if ("Caret".equals(a.getSubtype())) {
                // PDAnnotationCaret.getRectDifferences returns float[0] when
                // /RD is absent or non-array, never null.
                float[] rd = caretRd(a);
                return "rd=" + qpProj(rd);
            }
            return "n/a";
        } catch (Exception e) {
            return "ERR:" + e.getClass().getSimpleName();
        }
    }

    static float[] caretRd(PDAnnotation a) {
        try {
            return ((org.apache.pdfbox.pdmodel.interactive.annotation
                    .PDAnnotationCaret) a).getRectDifferences();
        } catch (Exception e) {
            return null;
        }
    }

    static void runCase(COSDictionary d, String name) {
        StringBuilder sb = new StringBuilder();
        sb.append("CASE ").append(name).append(' ');
        try {
            PDAnnotation a = PDAnnotation.createAnnotation(d);
            sb.append("class=").append(a.getClass().getSimpleName());
            sb.append(" acc=").append(accProj(a));
        } catch (Exception e) {
            sb.append("class=ERR:").append(e.getClass().getSimpleName());
        }
        out.println(sb.toString());
    }

    public static void main(String[] args) throws Exception {
        out = new PrintStream(System.out, true, "UTF-8");
        File dir = new File(args[0]);
        File pdf = new File(dir, "corpus.pdf");
        File manifest = new File(dir, "manifest.txt");
        String[] names =
                new String(java.nio.file.Files.readAllBytes(manifest.toPath()),
                                java.nio.charset.StandardCharsets.UTF_8)
                        .split("\n");
        String[] cleaned =
                Arrays.stream(names).map(String::trim).filter(s -> !s.isEmpty())
                        .toArray(String[]::new);
        try (PDDocument doc = Loader.loadPDF(pdf)) {
            COSDictionary catalog = doc.getDocumentCatalog().getCOSObject();
            COSBase fz =
                    catalog.getDictionaryObject(COSName.getPDFName("FuzzAnnots"));
            COSArray arr = (COSArray) fz;
            for (int i = 0; i < cleaned.length; i++) {
                COSBase entry = arr.getObject(i);
                COSDictionary d = entry instanceof COSDictionary
                        ? (COSDictionary) entry
                        : null;
                runCase(d, cleaned[i]);
            }
        }
    }
}
