import java.io.File;
import java.util.List;
import java.util.TreeSet;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSNumber;
import org.apache.pdfbox.cos.COSObject;
import org.apache.pdfbox.cos.COSStream;
import org.apache.pdfbox.pdfwriter.compress.CompressParameters;
import org.apache.pdfbox.pdmodel.PDDocument;

/**
 * Live oracle probe for PDFBox's COMPRESSED save (object streams + xref stream).
 *
 * Two modes:
 *
 *   save  in.pdf out.pdf   — load in.pdf and save it with PDFBox's compressed
 *                            writer: doc.save(out, new CompressParameters()).
 *                            In PDFBox 3.0 passing a (non-disabled)
 *                            CompressParameters routes through
 *                            COSWriterCompressionPool, packing eligible
 *                            non-stream indirect objects into /Type /ObjStm
 *                            and emitting a /Type /XRef cross-reference stream.
 *
 *   read  file.pdf         — emit structural facts (one "key=value" per line)
 *                            about an already-saved PDF:
 *                              objstm_count = number of /Type /ObjStm streams
 *                              xref_stream  = true|false (COSDocument flag)
 *                              packed       = objects living inside ObjStms
 *                                             (sum of each ObjStm's /N)
 *                              top_level    = indirect xref entries NOT packed
 *                                             into an ObjStm (type-1 records)
 *                              pages        = page count
 *                              cat_keys     = sorted catalog dictionary keys
 *
 * Usage:
 *   java -cp <pdfbox-app.jar>:<build> ObjStmSaveProbe save in.pdf out.pdf
 *   java -cp <pdfbox-app.jar>:<build> ObjStmSaveProbe read file.pdf
 */
public final class ObjStmSaveProbe {
    public static void main(String[] args) throws Exception {
        String mode = args[0];
        if ("save".equals(mode)) {
            doSave(args[1], args[2]);
        } else if ("read".equals(mode)) {
            doRead(args[1]);
        } else {
            throw new IllegalArgumentException("unknown mode: " + mode);
        }
    }

    private static void doSave(String in, String out) throws Exception {
        try (PDDocument doc = Loader.loadPDF(new File(in))) {
            // Non-disabled CompressParameters → compressed (ObjStm + XRef
            // stream) save path through COSWriterCompressionPool.
            doc.save(new File(out), new CompressParameters());
        }
    }

    private static void doRead(String file) throws Exception {
        try (PDDocument doc = Loader.loadPDF(new File(file))) {
            // /Type /ObjStm streams + total packed members (sum of /N).
            List<COSObject> objStms = doc.getDocument().getObjectsByType(COSName.OBJ_STM);
            int objstmCount = objStms.size();
            long packed = 0;
            for (COSObject obj : objStms) {
                COSBase base = obj.getObject();
                if (base instanceof COSStream) {
                    COSBase n = ((COSStream) base).getDictionaryObject(COSName.N);
                    if (n instanceof COSNumber) {
                        packed += ((COSNumber) n).intValue();
                    }
                }
            }

            boolean xrefStream = doc.getDocument().isXRefStream();

            // Top-level = xref entries that are NOT packed into an ObjStm.
            // The xref table maps every directly-addressed object to a byte
            // offset; packed (type-2) members are resolved through their
            // containing ObjStm and do not appear here, so this is the count
            // of objects living at the top level of the file body.
            int topLevel = doc.getDocument().getXrefTable().size();

            COSDictionary catalog =
                    (COSDictionary) doc.getDocument().getTrailer().getDictionaryObject(COSName.ROOT);
            TreeSet<String> keys = new TreeSet<>();
            for (COSName k : catalog.keySet()) {
                keys.add(k.getName());
            }
            StringBuilder catKeys = new StringBuilder();
            boolean first = true;
            for (String k : keys) {
                if (!first) {
                    catKeys.append(",");
                }
                catKeys.append(k);
                first = false;
            }

            StringBuilder sb = new StringBuilder();
            sb.append("objstm_count=").append(objstmCount).append("\n");
            sb.append("xref_stream=").append(xrefStream).append("\n");
            sb.append("packed=").append(packed).append("\n");
            sb.append("top_level=").append(topLevel).append("\n");
            sb.append("pages=").append(doc.getNumberOfPages()).append("\n");
            sb.append("cat_keys=").append(catKeys).append("\n");
            System.out.print(sb);
        }
    }
}
