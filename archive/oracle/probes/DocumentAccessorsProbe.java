import java.io.File;
import java.io.PrintStream;

import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.encryption.AccessPermission;

/**
 * Live oracle probe: emit Apache PDFBox's view of the document-level
 * accessors on {@link org.apache.pdfbox.pdmodel.PDDocument} — the
 * "top-of-the-object-graph" surface that downstream tooling reads first.
 *
 * <p>Covered accessors (PDFBox 3.0.7):
 * <ul>
 *   <li>{@code getNumberOfPages()} — the cached {@code /Pages /Count}.</li>
 *   <li>{@code getPage(int)} — 0-based; we resolve page 0 and assert it is
 *       non-null, plus probe an out-of-range index to confirm the document
 *       signals an error rather than returning a page.</li>
 *   <li>{@code isEncrypted()} / {@code isAllSecurityToBeRemoved()} — the two
 *       security toggles.</li>
 *   <li>{@code getCurrentAccessPermission()} — for an unencrypted document
 *       this is the full-owner permission object; we emit three of its
 *       booleans so the test can pin the "no restrictions" default.</li>
 *   <li>{@code getSignatureFields().size()} — count of {@code /FT /Sig}
 *       fields reachable from {@code /AcroForm}.</li>
 *   <li>{@code getSignatureDictionaries().size()} — count of those fields
 *       whose {@code /V} signature dictionary is set.</li>
 * </ul>
 *
 * Usage: java -cp &lt;pdfbox-app.jar&gt;:&lt;build&gt; DocumentAccessorsProbe input.pdf
 *
 * Output (UTF-8, stdout, line-oriented, no framing):
 *   numberOfPages=&lt;int&gt;
 *   page0NotNull=&lt;true|false&gt;
 *   pageOutOfRange=&lt;RAISE|RETURN&gt;
 *   isEncrypted=&lt;true|false&gt;
 *   isAllSecurityToBeRemoved=&lt;true|false&gt;
 *   accessPermNotNull=&lt;true|false&gt;
 *   canPrint=&lt;true|false&gt;
 *   canModify=&lt;true|false&gt;
 *   canExtractContent=&lt;true|false&gt;
 *   signatureFields=&lt;int&gt;
 *   signatureDictionaries=&lt;int&gt;
 */
public final class DocumentAccessorsProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            int n = doc.getNumberOfPages();
            out.println("numberOfPages=" + n);

            PDPage page0 = doc.getPage(0);
            out.println("page0NotNull=" + (page0 != null));

            // Out-of-range page index: PDFBox surfaces an exception rather
            // than handing back a page. We classify the outcome.
            String oor;
            try {
                doc.getPage(n);
                oor = "RETURN";
            } catch (RuntimeException e) {
                oor = "RAISE";
            }
            out.println("pageOutOfRange=" + oor);

            out.println("isEncrypted=" + doc.isEncrypted());
            out.println("isAllSecurityToBeRemoved=" + doc.isAllSecurityToBeRemoved());

            AccessPermission perm = doc.getCurrentAccessPermission();
            out.println("accessPermNotNull=" + (perm != null));
            out.println("canPrint=" + perm.canPrint());
            out.println("canModify=" + perm.canModify());
            out.println("canExtractContent=" + perm.canExtractContent());

            out.println("signatureFields=" + doc.getSignatureFields().size());
            out.println("signatureDictionaries=" + doc.getSignatureDictionaries().size());
        }
    }
}
