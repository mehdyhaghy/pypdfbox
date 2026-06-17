import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.InputStream;
import java.io.PrintStream;
import java.util.Iterator;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDocument;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSObject;
import org.apache.pdfbox.cos.COSObjectKey;
import org.apache.pdfbox.cos.COSStream;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.text.PDFTextStripper;

/**
 * Live oracle probe for /Filter SHAPE leniency (ISO 32000-1 §7.4.2).
 *
 * The PDF spec allows /Filter on a stream dictionary to be either a single
 * COSName (e.g. "/Filter /FlateDecode") OR an array of COSName (e.g.
 * "/Filter [/FlateDecode]" or "[/ASCII85Decode /FlateDecode]"). PDFBox
 * normalises both shapes transparently — readers walk the dict, decode
 * through every chained filter, and surface identical decoded content
 * regardless of how the producer wrote the entry.
 *
 * This probe lets a differential test load the *same* content stream wrapped
 * in each /Filter shape and confirm pypdfbox lands on the identical (page
 * count / decoded content-stream length / extracted text) tuple PDFBox does.
 *
 * Output (one "key=value" per line on stdout):
 *
 *   pages=&lt;int&gt;                   PDDocument.getNumberOfPages().
 *   content_decoded_len=&lt;int&gt;     Sum over every untyped (i.e. /Contents-style)
 *                                  COSStream of its decoded body byte count.
 *                                  Typed streams (e.g. catalog, font descriptors,
 *                                  /ObjStm, /XRef) carry a /Type and are skipped
 *                                  so the metric stays focused on page content.
 *   first_filter_shape=&lt;name|array|none&gt;
 *                                  Shape of the FIRST counted stream's /Filter
 *                                  entry (name = single COSName; array = COSArray;
 *                                  none = absent).
 *   first_filter_list=&lt;csv&gt;       Chain names as PDFBox normalises them,
 *                                  comma-joined (empty when absent).
 *   text=&lt;one-line-trimmed&gt;       PDFTextStripper.getText() with whitespace runs
 *                                  collapsed and trimmed so the value stays on a
 *                                  single key=value line.
 *
 * Usage:
 *   java -cp &lt;pdfbox-app.jar&gt;:&lt;build&gt; FilterShapeProbe file.pdf
 */
public final class FilterShapeProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            int pages = doc.getNumberOfPages();
            int totalDecodedLen = 0;
            String firstShape = "none";
            String firstList = "";
            boolean firstSeen = false;

            COSDocument cosDoc = doc.getDocument();
            for (COSObjectKey key : cosDoc.getXrefTable().keySet()) {
                COSObject obj = cosDoc.getObjectFromPool(key);
                if (obj == null) {
                    continue;
                }
                COSBase base = obj.getObject();
                if (!(base instanceof COSStream)) {
                    continue;
                }
                COSStream s = (COSStream) base;
                COSBase typeEntry = s.getDictionaryObject(COSName.TYPE);
                // Skip typed streams (catalog, font descriptors, /ObjStm,
                // /XRef, etc.) so the decoded-length metric tracks the page
                // content streams the test fixtures are built around.
                if (typeEntry != null) {
                    continue;
                }
                try (InputStream src = s.createInputStream()) {
                    ByteArrayOutputStream sink = new ByteArrayOutputStream();
                    byte[] buf = new byte[8192];
                    int n;
                    while ((n = src.read(buf)) > 0) {
                        sink.write(buf, 0, n);
                    }
                    totalDecodedLen += sink.size();
                }
                if (!firstSeen) {
                    firstSeen = true;
                    COSBase filters = s.getFilters();
                    StringBuilder sb = new StringBuilder();
                    if (filters == null) {
                        firstShape = "none";
                    } else if (filters instanceof COSName) {
                        firstShape = "name";
                        sb.append(((COSName) filters).getName());
                    } else if (filters instanceof COSArray) {
                        firstShape = "array";
                        COSArray array = (COSArray) filters;
                        boolean first = true;
                        Iterator<COSBase> it = array.iterator();
                        while (it.hasNext()) {
                            COSBase entry = it.next();
                            if (entry instanceof COSName) {
                                if (!first) {
                                    sb.append(",");
                                }
                                sb.append(((COSName) entry).getName());
                                first = false;
                            }
                        }
                    }
                    firstList = sb.toString();
                }
            }

            String text = new PDFTextStripper().getText(doc);
            String oneLine = text.replaceAll("\\s+", " ").trim();

            out.print("pages=" + pages + "\n");
            out.print("content_decoded_len=" + totalDecodedLen + "\n");
            out.print("first_filter_shape=" + firstShape + "\n");
            out.print("first_filter_list=" + firstList + "\n");
            out.print("text=" + oneLine + "\n");
        }
    }
}
