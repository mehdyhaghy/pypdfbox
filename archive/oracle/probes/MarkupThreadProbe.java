import java.io.File;
import java.io.PrintStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotation;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationMarkup;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationPopup;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationText;

/**
 * Live oracle probe for MARKUP ANNOTATION THREADING + REVIEW STATE.
 *
 * Surface: PDAnnotationMarkup review-workflow fields and the PDAnnotationPopup
 * back-link — /Popup (the linked popup, its /Open state + /Parent back-link),
 * /IRT (in-reply-to annotation reference, resolved to WHICH annotation it
 * replies to), /RT (reply type R vs Group), /State + /StateModel review state,
 * /Subj subject, /CreationDate.
 *
 * read mode only (pypdfbox authors the PDF; this probe re-reads ANY markup-
 * threaded PDF and emits the canonical per-annotation fingerprint below).
 *
 *   java ... MarkupThreadProbe read out.pdf
 *
 * Each annotation in page /Annots order is keyed by its /Contents string,
 * which the pypdfbox build makes unique per annotation. /IRT and /Popup /Parent
 * back-links are resolved to the /Contents of their target annotation — a
 * writer-independent identity that proves WHICH annotation a reply points at
 * (object numbers can differ between writers; /Contents cannot).
 *
 * Emits, per annotation:
 *
 *   ANNOT <subtype>
 *   CONTENTS <contents>                              (or "CONTENTS none")
 *   SUBJ <subject>                                   (or "SUBJ none")
 *   CREATIONDATE <raw /CreationDate string>          (or "CREATIONDATE none")
 *   RT <reply type>                                  (always present; default R)
 *   IRT <contents of target annotation>              (or "IRT none")
 *   STATE <state>                                    (or "STATE none")
 *   STATEMODEL <state model>                         (or "STATEMODEL none")
 *   POPUP <"yes"|"none">
 *   POPUPOPEN <"true"|"false">                       (only when POPUP yes)
 *   POPUPPARENT <contents of parent annotation>      (only when POPUP yes; or "none")
 *   END
 */
public final class MarkupThreadProbe {
    public static void main(String[] args) throws Exception {
        String mode = args[0];
        File file = new File(args[1]);
        if ("read".equals(mode)) {
            read(file);
        } else {
            throw new IllegalArgumentException("unknown mode: " + mode);
        }
    }

    private static void read(File file) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        StringBuilder sb = new StringBuilder();
        try (PDDocument doc = Loader.loadPDF(file)) {
            for (PDPage page : doc.getPages()) {
                for (PDAnnotation annot : page.getAnnotations()) {
                    emit(sb, annot);
                }
            }
        }
        out.print(sb);
    }

    private static String orNone(String v) {
        return v == null ? "none" : v;
    }

    /** Resolve a markup annotation dict to its /Contents string, or "none". */
    private static String contentsOf(COSDictionary dict) {
        if (dict == null) {
            return "none";
        }
        String c = dict.getString(COSName.CONTENTS);
        return c == null ? "none" : c;
    }

    private static void emit(StringBuilder sb, PDAnnotation annot) throws Exception {
        String subtype = annot.getSubtype();
        sb.append("ANNOT ").append(subtype == null ? "?" : subtype).append('\n');
        sb.append("CONTENTS ").append(orNone(annot.getContents())).append('\n');

        if (annot instanceof PDAnnotationMarkup) {
            PDAnnotationMarkup markup = (PDAnnotationMarkup) annot;

            sb.append("SUBJ ").append(orNone(markup.getSubject())).append('\n');

            // Raw /CreationDate string straight off the COS dict — pypdfbox's
            // get_creation_date returns the raw PDF date string, so compare raw
            // strings (date PARSING parity is checked separately in the test via
            // get_date / DateConverter).
            String rawCreation = markup.getCOSObject().getString(COSName.CREATION_DATE);
            sb.append("CREATIONDATE ").append(orNone(rawCreation)).append('\n');

            sb.append("RT ").append(markup.getReplyType()).append('\n');

            // /IRT resolved to the /Contents of the target annotation it
            // replies to (writer-independent identity).
            PDAnnotation irt = markup.getInReplyTo();
            if (irt != null) {
                sb.append("IRT ").append(contentsOf(irt.getCOSObject())).append('\n');
            } else {
                sb.append("IRT none\n");
            }

            sb.append("POPUP ");
            PDAnnotationPopup popup = markup.getPopup();
            if (popup != null) {
                sb.append("yes\n");
                sb.append("POPUPOPEN ").append(popup.getOpen() ? "true" : "false").append('\n');
                COSDictionary parent = popup.getCOSObject().getCOSDictionary(COSName.PARENT);
                if (parent == null) {
                    parent = popup.getCOSObject().getCOSDictionary(COSName.P);
                }
                sb.append("POPUPPARENT ").append(contentsOf(parent)).append('\n');
            } else {
                sb.append("none\n");
            }
        }

        // /State + /StateModel live on PDAnnotationText (the Text sticky-note
        // subtype), not on the markup base — read them off the COS dict so any
        // markup subtype carrying them is fingerprinted uniformly.
        String state = annot.getCOSObject().getString(COSName.getPDFName("State"));
        String stateModel = annot.getCOSObject().getString(COSName.getPDFName("StateModel"));
        sb.append("STATE ").append(orNone(state)).append('\n');
        sb.append("STATEMODEL ").append(orNone(stateModel)).append('\n');

        sb.append("END\n");
    }
}
