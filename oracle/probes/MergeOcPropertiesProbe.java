import java.io.File;
import java.io.PrintStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSObject;
import org.apache.pdfbox.multipdf.PDFMergerUtility;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDDocumentCatalog;

/**
 * Live oracle probe: merge N source PDFs that each carry an /OCProperties
 * (optional-content / layers) dictionary via Apache PDFBox's
 * {@link PDFMergerUtility#mergeDocuments}, save and reload, then emit a
 * deterministic projection of the MERGED /OCProperties so pypdfbox's merge of
 * the same surface can be diffed against PDFBox.
 *
 * This pins {@code PDFMergerUtility}'s /OCProperties merge, which goes through
 * {@code PDFCloneUtility.cloneMergeCOSBase}: when the destination already has
 * an /OCProperties, the source /OCGs array entries are *appended* (no dedup by
 * /Name, so two sources each naming a layer "Layer1" yield two groups), and the
 * /D default-config sub-dictionary is merged element-wise (dest wins on scalar
 * keys like /Name; the /ON, /OFF, /Order arrays concatenate).
 *
 * Usage:
 *   java -cp <pdfbox-app.jar>:<build> MergeOcPropertiesProbe out.pdf in1.pdf in2.pdf ...
 *
 * Output (UTF-8, LF-terminated lines):
 *   OCGS_COUNT=<n>                       (length of merged /OCProperties/OCGs)
 *   OCG <i> name=<name>                  (one per /OCGs entry, array order)
 *   D_NAME=<defaultConfigName|null>      (/OCProperties/D/Name)
 *   D_ON_COUNT=<n>                       (length of /D/ON, -1 if absent)
 *   D_OFF_COUNT=<n>                      (length of /D/OFF, -1 if absent)
 *   D_ORDER_COUNT=<n>                    (length of /D/Order, -1 if absent)
 * If the merged catalog has no /OCProperties: the single line NO_OCPROPERTIES.
 */
public final class MergeOcPropertiesProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        File output = new File(args[0]);

        PDFMergerUtility merger = new PDFMergerUtility();
        for (int i = 1; i < args.length; i++) {
            merger.addSource(new File(args[i]));
        }
        merger.setDestinationFileName(output.getAbsolutePath());
        merger.mergeDocuments(null);

        try (PDDocument merged = Loader.loadPDF(output)) {
            PDDocumentCatalog catalog = merged.getDocumentCatalog();
            COSDictionary cat = catalog.getCOSObject();
            COSBase ocpBase = cat.getDictionaryObject(COSName.getPDFName("OCProperties"));
            if (!(ocpBase instanceof COSDictionary)) {
                out.println("NO_OCPROPERTIES");
                return;
            }
            COSDictionary ocp = (COSDictionary) ocpBase;
            StringBuilder sb = new StringBuilder();

            COSArray ocgs = asArray(ocp.getDictionaryObject(COSName.getPDFName("OCGs")));
            int count = ocgs == null ? 0 : ocgs.size();
            sb.append("OCGS_COUNT=").append(count).append('\n');
            for (int i = 0; i < count; i++) {
                COSBase e = ocgs.getObject(i);
                String name = "";
                if (e instanceof COSDictionary) {
                    name = ((COSDictionary) e).getString(COSName.getPDFName("Name"), "");
                }
                sb.append("OCG ").append(i).append(" name=").append(esc(name)).append('\n');
            }

            COSBase dBase = ocp.getDictionaryObject(COSName.getPDFName("D"));
            if (dBase instanceof COSDictionary) {
                COSDictionary d = (COSDictionary) dBase;
                String dName = d.getString(COSName.getPDFName("Name"));
                sb.append("D_NAME=").append(dName == null ? "null" : esc(dName)).append('\n');
                sb.append("D_ON_COUNT=").append(arrLen(d, "ON")).append('\n');
                sb.append("D_OFF_COUNT=").append(arrLen(d, "OFF")).append('\n');
                sb.append("D_ORDER_COUNT=").append(arrLen(d, "Order")).append('\n');
            } else {
                sb.append("D_NAME=null\n");
                sb.append("D_ON_COUNT=-1\n");
                sb.append("D_OFF_COUNT=-1\n");
                sb.append("D_ORDER_COUNT=-1\n");
            }
            out.print(sb);
        }
    }

    private static COSArray asArray(COSBase b) {
        if (b instanceof COSObject) {
            b = ((COSObject) b).getObject();
        }
        return b instanceof COSArray ? (COSArray) b : null;
    }

    private static int arrLen(COSDictionary d, String key) {
        COSArray a = asArray(d.getDictionaryObject(COSName.getPDFName(key)));
        return a == null ? -1 : a.size();
    }

    private static String esc(String s) {
        StringBuilder b = new StringBuilder(s.length());
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            switch (c) {
                case '\\': b.append("\\\\"); break;
                case '\n': b.append("\\n"); break;
                case '\r': b.append("\\r"); break;
                case '\t': b.append("\\t"); break;
                default: b.append(c);
            }
        }
        return b.toString();
    }
}
