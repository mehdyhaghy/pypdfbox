import java.io.File;
import java.io.PrintStream;
import java.util.List;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.multipdf.PDFMergerUtility;
import org.apache.pdfbox.pdfwriter.compress.CompressParameters;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.PDPageTree;

/**
 * Live oracle probe: merge N input PDFs via {@link PDFMergerUtility}, saving the
 * destination UNCOMPRESSED (traditional xref table + flat bodies, the matched
 * strategy pypdfbox's default {@code PDDocument.save} uses), then reload and emit
 * the ORDERED KEY LIST of every merged page dictionary plus the load-bearing
 * facts pypdfbox's wave-1508 byte-parity pins assert: materialized /CropBox
 * presence, the /Parent key's position, and the /CropBox value.
 *
 * This goes deeper than {@code MergeObjectGeometryProbe} (which only pins object
 * numbering + /Type roles): it captures PER-PAGE-DICT key INSERTION ORDER, which
 * is exactly what determines whether a merged page serializes byte-for-byte the
 * way PDFBox serializes it. PDFBox's appendDocument page loop runs setCropBox /
 * setMediaBox / setRotation / setResources unconditionally, materializing a
 * /CropBox the raw clone lacked when the source only inherited one; this probe
 * exposes the resulting key order so pypdfbox can match it.
 *
 * Usage:
 *   java -cp <jar>:<build> MergePageDictOrderProbe out.pdf in1 in2 ...
 *
 * Output (UTF-8, LF-terminated):
 *   pages <count>
 *   page <i> keys <K1>,<K2>,...        (page-dict key order, COSName local parts)
 *   page <i> crop <x0> <y0> <x1> <y1>  (materialized /CropBox, or "none")
 *   page <i> parent_index <n>          (0-based index of /Parent in key order, -1 if absent)
 */
public final class MergePageDictOrderProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        File output = new File(args[0]);

        PDFMergerUtility merger = new PDFMergerUtility();
        for (int i = 1; i < args.length; i++) {
            merger.addSource(new File(args[i]));
        }
        merger.setDestinationFileName(output.getAbsolutePath());
        merger.mergeDocuments(null, CompressParameters.NO_COMPRESSION);

        try (PDDocument merged = Loader.loadPDF(output)) {
            PDPageTree pages = merged.getPages();
            int total = merged.getNumberOfPages();
            out.println("pages " + total);
            int idx = 0;
            for (PDPage page : pages) {
                COSDictionary dict = page.getCOSObject();
                List<COSName> keys = new java.util.ArrayList<>(dict.keySet());
                StringBuilder sb = new StringBuilder();
                int parentIndex = -1;
                for (int k = 0; k < keys.size(); k++) {
                    if (k > 0) {
                        sb.append(',');
                    }
                    sb.append(keys.get(k).getName());
                    if (keys.get(k).equals(COSName.PARENT)) {
                        parentIndex = k;
                    }
                }
                out.println("page " + idx + " keys " + sb);

                COSBase crop = dict.getDictionaryObject(COSName.CROP_BOX);
                if (crop instanceof org.apache.pdfbox.cos.COSArray) {
                    org.apache.pdfbox.cos.COSArray a =
                        (org.apache.pdfbox.cos.COSArray) crop;
                    out.println("page " + idx + " crop "
                        + fmt(a, 0) + " " + fmt(a, 1) + " "
                        + fmt(a, 2) + " " + fmt(a, 3));
                } else {
                    out.println("page " + idx + " crop none");
                }
                out.println("page " + idx + " parent_index " + parentIndex);
                idx++;
            }
        }
    }

    private static String fmt(org.apache.pdfbox.cos.COSArray a, int i) {
        float f = ((org.apache.pdfbox.cos.COSNumber) a.get(i)).floatValue();
        return Integer.toHexString(Float.floatToIntBits(f));
    }
}
