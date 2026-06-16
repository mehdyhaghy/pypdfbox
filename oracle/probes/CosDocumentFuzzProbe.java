import java.io.PrintStream;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSDocument;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSObject;
import org.apache.pdfbox.cos.COSObjectKey;

/**
 * Differential fuzz probe for the Apache PDFBox 3.0.7 document-level COS
 * container — {@code org.apache.pdfbox.cos.COSDocument}. Wave 1537, agent B.
 *
 * <p>No bytes are parsed here: the probe builds {@code COSDocument} instances
 * directly and exercises the document-level accessors on a FRESH / EMPTY
 * document and around the lifecycle ({@code close} / re-close / use-after-close)
 * — the corners a real parse never reaches but the writer + recovery paths do.
 *
 * <p>Each result is projected as a {@code KEY=VALUE} line (LF-terminated, in a
 * stable order); an exception is projected as {@code KEY=ERR:<SimpleName>}.
 * The pypdfbox sibling ({@code tests/cos/oracle/
 * test_cos_document_fuzz_wave1537.py}) reproduces the same probe surface and
 * either asserts byte-identical projections (alignable) or pins BOTH sides of a
 * deliberate divergence (the upstream NPE-on-null-trailer cases where pypdfbox
 * is intentionally hardened to return {@code None} / auto-create a trailer).
 *
 * <h2>Covered surface</h2>
 * <ul>
 *   <li>fresh defaults — {@code getVersion} (1.4), {@code getTrailer} (null),
 *       {@code isEncrypted}/{@code isDecrypted}/{@code isClosed}/
 *       {@code isXRefStream}/{@code hasHybridXRef} (false),
 *       {@code getHighestXRefObjectNumber}/{@code getStartXref} (0),
 *       {@code getLinearizedDictionary} (null);</li>
 *   <li>null-trailer accessors — {@code getDocumentID},
 *       {@code getEncryptionDictionary}, {@code setDocumentID},
 *       {@code setEncryptionDictionary}, {@code setTrailer(null)} (all NPE
 *       upstream);</li>
 *   <li>{@code getObjectsByType} for an absent type (empty list);</li>
 *   <li>{@code getObjectFromPool} — fresh key (placeholder), repeat-key identity,
 *       null key;</li>
 *   <li>{@code setVersion} — downgrade, zero, negative (all stored verbatim);
 *       {@code setStartXref}/{@code setHighestXRefObjectNumber} negative;</li>
 *   <li>lifecycle — double {@code close}, {@code getObjectFromPool} /
 *       {@code getObjectsByType} / {@code getVersion} after close;</li>
 *   <li>{@code setDecrypted} one-way flip.</li>
 * </ul>
 */
public final class CosDocumentFuzzProbe {

    static PrintStream out;

    interface Producer {
        String run() throws Throwable;
    }

    static void line(String key, Producer p) {
        String v;
        try {
            v = p.run();
        } catch (Throwable e) {
            v = "ERR:" + e.getClass().getSimpleName();
        }
        out.println(key + "=" + v);
    }

    static String nn(Object o) {
        return o == null ? "null" : "nonnull";
    }

    public static void main(String[] args) throws Exception {
        out = new PrintStream(System.out, true, "UTF-8");

        // ---- fresh defaults ----
        line("version", () -> Float.toString(new COSDocument().getVersion()));
        line("trailer", () -> nn(new COSDocument().getTrailer()));
        line("isEncrypted", () -> Boolean.toString(new COSDocument().isEncrypted()));
        line("isDecrypted", () -> Boolean.toString(new COSDocument().isDecrypted()));
        line("isClosed", () -> Boolean.toString(new COSDocument().isClosed()));
        line("isXRefStream", () -> Boolean.toString(new COSDocument().isXRefStream()));
        line("hasHybridXRef", () -> Boolean.toString(new COSDocument().hasHybridXRef()));
        line("highestXRef", () -> Long.toString(new COSDocument().getHighestXRefObjectNumber()));
        line("startXref", () -> Long.toString(new COSDocument().getStartXref()));
        line("linearized", () -> nn(new COSDocument().getLinearizedDictionary()));

        // ---- null-trailer accessors (NPE upstream) ----
        line("docIdNoTrailer", () -> nn(new COSDocument().getDocumentID()));
        line("encDictNoTrailer", () -> nn(new COSDocument().getEncryptionDictionary()));
        line("setDocIdNoTrailer", () -> {
            COSDocument d = new COSDocument();
            d.setDocumentID(new COSArray());
            return nn(d.getTrailer());
        });
        line("setEncNoTrailer", () -> {
            COSDocument d = new COSDocument();
            d.setEncryptionDictionary(new COSDictionary());
            return nn(d.getTrailer());
        });
        line("setTrailerNull", () -> {
            COSDocument d = new COSDocument();
            d.setTrailer(new COSDictionary());
            d.setTrailer(null);
            return nn(d.getTrailer());
        });

        // ---- getObjectsByType absent ----
        line("byTypeAbsentSize",
                () -> Integer.toString(
                        new COSDocument().getObjectsByType(COSName.getPDFName("Nope")).size()));

        // ---- getObjectFromPool ----
        line("poolFresh", () -> {
            COSObject o = new COSDocument().getObjectFromPool(new COSObjectKey(5, 0));
            return o == null ? "null" : ("n=" + o.getObjectNumber() + ",g=" + o.getGenerationNumber());
        });
        line("poolSame", () -> {
            COSDocument d = new COSDocument();
            COSObject a = d.getObjectFromPool(new COSObjectKey(5, 0));
            COSObject b = d.getObjectFromPool(new COSObjectKey(5, 0));
            return Boolean.toString(a == b);
        });
        line("poolNull", () -> nn(new COSDocument().getObjectFromPool(null)));

        // ---- setVersion / xref-number leniency ----
        line("downgrade", () -> {
            COSDocument d = new COSDocument();
            d.setVersion(1.7f);
            d.setVersion(1.3f);
            return Float.toString(d.getVersion());
        });
        line("downgradeFromDefault", () -> {
            COSDocument d = new COSDocument();
            d.setVersion(1.2f);
            return Float.toString(d.getVersion());
        });
        line("setVerZero", () -> {
            COSDocument d = new COSDocument();
            d.setVersion(0f);
            return Float.toString(d.getVersion());
        });
        line("setVerNeg", () -> {
            COSDocument d = new COSDocument();
            d.setVersion(-1f);
            return Float.toString(d.getVersion());
        });
        line("highestNeg", () -> {
            COSDocument d = new COSDocument();
            d.setHighestXRefObjectNumber(-5);
            return Long.toString(d.getHighestXRefObjectNumber());
        });
        line("startNeg", () -> {
            COSDocument d = new COSDocument();
            d.setStartXref(-3);
            return Long.toString(d.getStartXref());
        });

        // ---- lifecycle ----
        line("doubleClose", () -> {
            COSDocument d = new COSDocument();
            d.close();
            boolean c1 = d.isClosed();
            d.close();
            boolean c2 = d.isClosed();
            return c1 + "," + c2;
        });
        line("poolAfterClose", () -> {
            COSDocument d = new COSDocument();
            d.close();
            return nn(d.getObjectFromPool(new COSObjectKey(1, 0)));
        });
        line("byTypeAfterClose", () -> {
            COSDocument d = new COSDocument();
            d.close();
            return Integer.toString(d.getObjectsByType(COSName.getPDFName("Page")).size());
        });
        line("versionAfterClose", () -> {
            COSDocument d = new COSDocument();
            d.close();
            return Float.toString(d.getVersion());
        });

        // ---- setDecrypted one-way ----
        line("afterSetDecrypted", () -> {
            COSDocument d = new COSDocument();
            d.setDecrypted();
            return Boolean.toString(d.isDecrypted());
        });
    }
}
