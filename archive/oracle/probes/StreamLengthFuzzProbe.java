import java.io.File;
import java.io.InputStream;
import java.io.PrintStream;
import java.util.Arrays;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDocument;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSNull;
import org.apache.pdfbox.cos.COSNumber;
import org.apache.pdfbox.cos.COSObject;
import org.apache.pdfbox.cos.COSObjectKey;
import org.apache.pdfbox.cos.COSStream;
import org.apache.pdfbox.pdmodel.PDDocument;

/**
 * Differential fuzz probe for the Apache PDFBox 3.0.7 COS STREAM length /
 * endstream recovery core — {@code org.apache.pdfbox.pdfparser.BaseParser
 * .parseCOSStream} and the {@code COSParser} helpers it dispatches to
 * ({@code getLength}, {@code validateStreamLength},
 * {@code readUntilEndStream(EndstreamFilterStream)}), as actually reached
 * from a real document body parse ({@code COSParser.parseFileObject} resolving
 * an indirect stream object lazily). Wave 1517, agent A.
 *
 * <p>This exercises the surface where {@code /Length} is wrong / indirect /
 * missing / negative, where the {@code endstream} / {@code endobj} keyword is
 * absent or misplaced, brute-force endstream scanning, trailing-whitespace
 * handling before {@code endstream}, and length-vs-actual mismatch recovery.
 *
 * <h2>Input (file-driven manifest, same pattern as CosObjectParseFuzzProbe)</h2>
 * The pypdfbox sibling
 * ({@code tests/pdfparser/test_stream_length_fuzz_wave1517.py}) writes a
 * deterministic corpus into a tmp dir: each case emits {@code <case>.pdf}, a
 * minimal PDF whose object {@code 1 0 obj} is a STREAM whose framing is the
 * raw fuzzed bytes, plus a valid catalog + pages tree so the document loads.
 * A {@code manifest.txt} (one case name per line, in order) drives both sides
 * over identical files.
 *
 * <h2>Output grammar (one UTF-8 LF-terminated line per case)</h2>
 * <pre>
 *   CASE &lt;name&gt; &lt;projection&gt;
 * </pre>
 * where projection is one of:
 * <pre>
 *   stream(raw=&lt;n&gt;,len=&lt;LengthDictValue|na&gt;,dec=&lt;m|none|ERR&gt;)
 *   notstream(&lt;COSClassSimpleName&gt;)   object 1 0 R resolved to a non-stream
 *   null                               resolved to COSNull / null
 *   ABSENT                             object 1 0 R not in the pool
 *   ERR:&lt;ExceptionSimpleName&gt;          resolving object 1 0 R threw
 *   LOAD:&lt;ExceptionSimpleName&gt;         Loader.loadPDF threw
 * </pre>
 * {@code raw} = decoded-or-raw body byte count exposed by
 * {@code COSStream.getLength()} (the recovered/declared raw body size);
 * {@code len} = the post-parse {@code /Length} entry value (a {@code COSNumber}
 * after recovery rewrites it, else {@code na}); {@code dec} = the byte count of
 * the fully-decoded body ({@code getInputStream}) or {@code ERR} if decoding
 * threw / {@code none} if the stream had no body.
 */
public final class StreamLengthFuzzProbe {

    static PrintStream out;

    static String exc(Throwable e) {
        return e.getClass().getSimpleName();
    }

    static String lenEntry(COSStream s) {
        COSBase l = s.getItem(COSName.LENGTH);
        if (l instanceof COSObject) {
            l = ((COSObject) l).getObject();
        }
        if (l instanceof COSNumber) {
            return Long.toString(((COSNumber) l).longValue());
        }
        return "na";
    }

    static String dec(COSStream s) {
        try (InputStream in = s.createInputStream()) {
            long total = 0;
            byte[] tmp = new byte[8192];
            int r;
            while ((r = in.read(tmp)) != -1) {
                total += r;
            }
            return Long.toString(total);
        } catch (Throwable e) {
            return "ERR";
        }
    }

    static String project(File pdf) {
        PDDocument doc = null;
        try {
            doc = Loader.loadPDF(pdf);
            COSDocument cos = doc.getDocument();
            COSObject obj = cos.getObjectFromPool(new COSObjectKey(1, 0));
            if (obj == null) {
                return "ABSENT";
            }
            COSBase resolved;
            try {
                resolved = obj.getObject();
            } catch (Throwable e) {
                return "ERR:" + exc(e);
            }
            if (resolved == null || resolved instanceof COSNull) {
                return "null";
            }
            if (!(resolved instanceof COSStream)) {
                return "notstream(" + resolved.getClass().getSimpleName() + ")";
            }
            COSStream s = (COSStream) resolved;
            long raw = s.getLength();
            return "stream(raw=" + raw + ",len=" + lenEntry(s)
                    + ",dec=" + dec(s) + ")";
        } catch (Throwable e) {
            return "LOAD:" + exc(e);
        } finally {
            if (doc != null) {
                try {
                    doc.close();
                } catch (Exception ignored) {
                    // best-effort close
                }
            }
        }
    }

    static void runCase(File dir, String name) {
        File pdf = new File(dir, name + ".pdf");
        out.println("CASE " + name + " " + project(pdf));
    }

    public static void main(String[] args) throws Exception {
        out = new PrintStream(System.out, true, "UTF-8");
        File dir = new File(args[0]);
        File manifest = new File(dir, "manifest.txt");
        String[] names =
                new String(java.nio.file.Files.readAllBytes(manifest.toPath()),
                                java.nio.charset.StandardCharsets.UTF_8)
                        .split("\n");
        Arrays.stream(names)
                .map(String::trim)
                .filter(s -> !s.isEmpty())
                .forEach(name -> runCase(dir, name));
    }
}
