import java.io.File;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSNumber;
import org.apache.pdfbox.cos.COSObject;
import org.apache.pdfbox.pdfwriter.compress.CompressParameters;
import org.apache.pdfbox.pdmodel.PDDocument;

/**
 * Live oracle probe pinning the TRAILER-LEVEL consistency of a compressed
 * save's cross-reference stream (/Type /XRef).
 *
 * The sibling probes (ObjStmSaveProbe, CompressedSaveProbe) cover ObjStm
 * packing shape + text round-trip; this one isolates the trailer invariants
 * that make the XRef stream a valid *trailer* under ISO 32000-1 §7.5.8, read
 * off the parsed COSDocument so the facts are "what PDFBox accepted":
 *
 *   1. /Root — the document catalog reference. We emit its object number and
 *      whether it resolves to a /Type /Catalog dictionary. PDFBox refuses to
 *      load a file whose /Root is missing or non-catalog, so reaching doFacts
 *      already proves /Root is valid; root_objnum lets a test assert pypdfbox
 *      points /Root at the SAME catalog object PDFBox resolves.
 *   2. /Size — the parsed trailer /Size. Together with max_objnum (PDFBox's
 *      highest in-use object number from getHighestXRefObjectNumber), a test
 *      asserts /Size > every addressed object number (ISO 32000-1 §7.5.8.2:
 *      /Size is "1 greater than the highest object number").
 *
 * (/W and /Index are consumed during parse and not re-exposed on the parsed
 *  model, so their byte-level well-formedness + consistency with /Size is
 *  asserted directly against the output bytes in the paired Python test.)
 *
 * Modes (one "key=value" per line on stdout unless noted):
 *
 *   save  in.pdf out.pdf   — load in.pdf, save with PDFBox's compressed writer
 *                            (doc.save(out, new CompressParameters())). No
 *                            stdout.
 *
 *   facts file.pdf         — emit, for an already-saved PDF:
 *                              loadable        = true (reached => parsed ok)
 *                              xref_stream     = true|false (COSDocument flag)
 *                              root_objnum     = catalog indirect object number
 *                              root_is_catalog = /Root resolves to /Type/Catalog
 *                              size            = parsed trailer /Size
 *                              max_objnum      = highest in-use object number
 *                              size_gt_max     = (size > max_objnum)
 *                              pages           = page count
 *
 * Usage:
 *   java -cp <pdfbox-app.jar>:<build> XRefStreamTrailerProbe save  in.pdf out.pdf
 *   java -cp <pdfbox-app.jar>:<build> XRefStreamTrailerProbe facts file.pdf
 */
public final class XRefStreamTrailerProbe {
    public static void main(String[] args) throws Exception {
        String mode = args[0];
        if ("save".equals(mode)) {
            doSave(args[1], args[2]);
        } else if ("facts".equals(mode)) {
            doFacts(args[1]);
        } else {
            throw new IllegalArgumentException("unknown mode: " + mode);
        }
    }

    private static void doSave(String in, String out) throws Exception {
        try (PDDocument doc = Loader.loadPDF(new File(in))) {
            doc.save(new File(out), new CompressParameters());
        }
    }

    private static void doFacts(String file) throws Exception {
        try (PDDocument doc = Loader.loadPDF(new File(file))) {
            COSDictionary trailer = doc.getDocument().getTrailer();

            boolean xrefStream = doc.getDocument().isXRefStream();

            // /Root object number + catalog-ness.
            long rootObjnum = -1;
            boolean rootIsCatalog = false;
            COSBase rootRef = trailer.getItem(COSName.ROOT);
            if (rootRef instanceof COSObject) {
                rootObjnum = ((COSObject) rootRef).getObjectNumber();
            }
            COSBase rootBase = trailer.getDictionaryObject(COSName.ROOT);
            if (rootBase instanceof COSDictionary) {
                COSBase t = ((COSDictionary) rootBase).getItem(COSName.TYPE);
                rootIsCatalog = COSName.CATALOG.equals(t);
            }

            // /Size + highest in-use object number.
            long size = -1;
            COSBase sizeBase = trailer.getDictionaryObject(COSName.SIZE);
            if (sizeBase instanceof COSNumber) {
                size = ((COSNumber) sizeBase).intValue();
            }
            long maxObjnum = doc.getDocument().getHighestXRefObjectNumber();

            StringBuilder sb = new StringBuilder();
            sb.append("loadable=true\n");
            sb.append("xref_stream=").append(xrefStream).append("\n");
            sb.append("root_objnum=").append(rootObjnum).append("\n");
            sb.append("root_is_catalog=").append(rootIsCatalog).append("\n");
            sb.append("size=").append(size).append("\n");
            sb.append("max_objnum=").append(maxObjnum).append("\n");
            sb.append("size_gt_max=").append(size > maxObjnum).append("\n");
            sb.append("pages=").append(doc.getNumberOfPages()).append("\n");
            System.out.print(sb);
        }
    }
}
