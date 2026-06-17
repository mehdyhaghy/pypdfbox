import java.io.File;
import java.io.PrintStream;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSNumber;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDDocumentCatalog;
import org.apache.pdfbox.pdmodel.PageLayout;
import org.apache.pdfbox.pdmodel.PageMode;
import org.apache.pdfbox.pdmodel.interactive.viewerpreferences.PDViewerPreferences;

/**
 * Live oracle probe: emit Apache PDFBox's document-catalog viewer-level
 * metadata view of a PDF.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> ViewerPrefsProbe input.pdf
 *
 * Emits canonical, line-oriented output (UTF-8, stdout, no framing). One line
 * per viewer-preference / catalog property the pypdfbox surface exposes:
 *
 *   present=<bool>                       (/ViewerPreferences dictionary present)
 *   hideToolbar=<bool>
 *   hideMenubar=<bool>
 *   hideWindowUI=<bool>
 *   fitWindow=<bool>
 *   centerWindow=<bool>
 *   displayDocTitle=<bool>
 *   nonFullScreenPageMode=<enum-string>  (defaults to "UseNone" when absent)
 *   direction=<enum-string>              (defaults to "L2R" when absent)
 *   printScaling=<enum-string>           (defaults to "AppDefault" when absent)
 *   duplex=<enum-string-or-NULL>         (no spec default; NULL when absent)
 *   numCopies=<int>                      (raw /NumCopies; NULL when absent)
 *   printPageRange=<csv-or-NULL>         (raw /PrintPageRange flat ints, csv)
 *   pageLayout=<enum-string>             (catalog getPageLayout(); SinglePage default)
 *   pageMode=<enum-string>               (catalog getPageMode(); UseNone default)
 *   lang=<string-or-NULL>                (/Lang)
 *   version=<name-or-NULL>               (/Version override on the catalog)
 *
 * PDFBox 3.0.7's PDViewerPreferences exposes no getNumCopies / getPrintPageRange
 * accessor, so those two are read straight off the /ViewerPreferences COS
 * dictionary (the spec-correct /NumCopies integer and /PrintPageRange array).
 *
 * Boolean values render as the lowercase literals "true" / "false". A missing
 * name/string field renders as the literal "NULL".
 */
public final class ViewerPrefsProbe {

    private static String nz(String v) {
        return v == null ? "NULL" : v;
    }

    private static String b(boolean v) {
        return v ? "true" : "false";
    }

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            PDDocumentCatalog cat = doc.getDocumentCatalog();

            PDViewerPreferences vp = cat.getViewerPreferences();
            out.println("present=" + b(vp != null));
            if (vp != null) {
                out.println("hideToolbar=" + b(vp.hideToolbar()));
                out.println("hideMenubar=" + b(vp.hideMenubar()));
                out.println("hideWindowUI=" + b(vp.hideWindowUI()));
                out.println("fitWindow=" + b(vp.fitWindow()));
                out.println("centerWindow=" + b(vp.centerWindow()));
                out.println("displayDocTitle=" + b(vp.displayDocTitle()));
                out.println("nonFullScreenPageMode=" + nz(vp.getNonFullScreenPageMode()));
                out.println("direction=" + nz(vp.getReadingDirection()));
                out.println("printScaling=" + nz(vp.getPrintScaling()));
                out.println("duplex=" + nz(vp.getDuplex()));

                // /NumCopies and /PrintPageRange have no upstream getter in
                // PDFBox 3.0.7 — read them off the raw dictionary.
                COSDictionary vpDict = vp.getCOSObject();
                COSBase numCopies = vpDict.getDictionaryObject(COSName.getPDFName("NumCopies"));
                if (numCopies instanceof COSNumber) {
                    out.println("numCopies=" + ((COSNumber) numCopies).intValue());
                } else {
                    out.println("numCopies=NULL");
                }

                COSBase ppr = vpDict.getDictionaryObject(COSName.getPDFName("PrintPageRange"));
                if (ppr instanceof COSArray) {
                    COSArray arr = (COSArray) ppr;
                    StringBuilder sb = new StringBuilder();
                    for (int i = 0; i < arr.size(); i++) {
                        COSBase el = arr.getObject(i);
                        if (i > 0) {
                            sb.append(",");
                        }
                        if (el instanceof COSNumber) {
                            sb.append(((COSNumber) el).intValue());
                        } else {
                            sb.append("?");
                        }
                    }
                    out.println("printPageRange=" + sb.toString());
                } else {
                    out.println("printPageRange=NULL");
                }
            } else {
                out.println("hideToolbar=false");
                out.println("hideMenubar=false");
                out.println("hideWindowUI=false");
                out.println("fitWindow=false");
                out.println("centerWindow=false");
                out.println("displayDocTitle=false");
                out.println("nonFullScreenPageMode=NULL");
                out.println("direction=NULL");
                out.println("printScaling=NULL");
                out.println("duplex=NULL");
                out.println("numCopies=NULL");
                out.println("printPageRange=NULL");
            }

            PageLayout layout = cat.getPageLayout();
            out.println("pageLayout=" + (layout == null ? "NULL" : layout.stringValue()));

            PageMode mode = cat.getPageMode();
            out.println("pageMode=" + (mode == null ? "NULL" : mode.stringValue()));

            out.println("lang=" + nz(cat.getLanguage()));
            out.println("version=" + nz(cat.getVersion()));
        }
    }
}
