import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.interactive.digitalsignature.PDSignature;
import org.apache.pdfbox.pdmodel.interactive.digitalsignature.SignatureOptions;

import java.io.ByteArrayOutputStream;

/**
 * Differential probe for PDDocument IllegalStateException guards:
 *   - addSignature on an empty (0-page) document -> "Cannot sign an empty document"
 *   - saveIncremental on a created (no source) document -> "document was not
 *     loaded from a file or a stream"
 *   - saveIncrementalForExternalSigning on a created document -> source check
 *     fires first -> "document was not loaded from a file or a stream"
 *
 * Prints, per operation, NO_THROW or the exception class+message.
 */
public class PDDocumentSignStateProbe
{
    static String desc(Throwable t)
    {
        return t.getClass().getName() + "|" + t.getMessage();
    }

    public static void main(String[] args) throws Exception
    {
        // ---- addSignature on empty document (no pages) ----
        {
            PDDocument doc = new PDDocument();
            PDSignature sig = new PDSignature();
            try {
                doc.addSignature(sig, new SignatureOptions());
                System.out.println("addSignature_empty=NO_THROW");
            } catch (Throwable e) {
                System.out.println("addSignature_empty=" + desc(e));
            }
            doc.close();
        }

        // ---- saveIncremental on created (no source) document ----
        {
            PDDocument doc = new PDDocument();
            doc.addPage(new PDPage());
            ByteArrayOutputStream sink = new ByteArrayOutputStream();
            try {
                doc.saveIncremental(sink);
                System.out.println("saveIncremental_nosource=NO_THROW");
            } catch (Throwable e) {
                System.out.println("saveIncremental_nosource=" + desc(e));
            }
            doc.close();
        }

        // ---- saveIncrementalForExternalSigning on created (no source) ----
        {
            PDDocument doc = new PDDocument();
            doc.addPage(new PDPage());
            ByteArrayOutputStream sink = new ByteArrayOutputStream();
            try {
                doc.saveIncrementalForExternalSigning(sink);
                System.out.println("saveIncrExtSign_nosource=NO_THROW");
            } catch (Throwable e) {
                System.out.println("saveIncrExtSign_nosource=" + desc(e));
            }
            doc.close();
        }
    }
}
