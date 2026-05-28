import java.io.File;
import java.io.PrintStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;

/**
 * Live oracle probe: emit a canonical per-page listing of the page's
 * annotation tab-order entry — both the raw ``/Tabs`` COS name (or
 * ``none`` when absent) and the value that pypdfbox's ``get_tab_order()``
 * is expected to surface.
 *
 * PDFBox 3.0.7's ``PDPage`` has no native ``getTabOrder()`` / ``setTabOrder()``
 * accessor (those landed later upstream), so the canonical truth here is the
 * direct ``/Tabs`` COS name lookup via
 * ``page.getCOSObject().getNameAsString(COSName.TABS_NAME)``.  pypdfbox's
 * ``PDPage.get_tab_order()`` returns the same raw name string (or ``None``
 * when absent), so the two surfaces compare byte-for-byte.
 *
 * Output (UTF-8, LF-terminated), one block per page:
 *
 *   page <index> tabs <raw|none> order <raw|none>
 *
 * ``raw`` is the single-letter name written into ``/Tabs`` (``R``/``C``/``S``/
 * ``A``/``W`` per PDF 32000-1 §12.5 plus PDF 2.0 additions), ``none`` when
 * absent (PDFBox treats the missing entry as the default — no tab order is
 * imposed by the page).
 */
public final class PageTabsProbe {

    private static final COSName TABS_NAME = COSName.getPDFName("Tabs");

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        if (args.length < 1) {
            System.err.println("usage: PageTabsProbe <pdf>");
            System.exit(2);
        }
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            StringBuilder sb = new StringBuilder();
            int index = 0;
            for (PDPage page : doc.getPages()) {
                COSDictionary cos = page.getCOSObject();
                String raw = readTabs(cos);
                sb.append("page ").append(index)
                        .append(" tabs ").append(raw == null ? "none" : raw)
                        .append(" order ").append(raw == null ? "none" : raw)
                        .append('\n');
                index++;
            }
            out.print(sb);
        }
    }

    /** Read ``/Tabs`` as a name string. Returns ``null`` when absent or
     *  when the entry is not a COSName (PDFBox's ``getNameAsString`` would
     *  also coerce a COSString to text, but ``/Tabs`` is spec-required to
     *  be a name — reject other shapes so the parity is exact). */
    private static String readTabs(COSDictionary cos) {
        COSBase value = cos.getDictionaryObject(TABS_NAME);
        if (value instanceof COSName) {
            return ((COSName) value).getName();
        }
        return null;
    }
}
