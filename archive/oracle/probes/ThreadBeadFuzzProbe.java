import java.io.PrintStream;
import java.util.IdentityHashMap;
import java.util.List;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSNull;
import org.apache.pdfbox.cos.COSObject;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDDocumentInformation;
import org.apache.pdfbox.pdmodel.interactive.pagenavigation.PDThread;
import org.apache.pdfbox.pdmodel.interactive.pagenavigation.PDThreadBead;

/**
 * Differential fuzz probe for article-thread/bead RING TRAVERSAL, the catalog
 * {@code /Threads} collection, and {@code /I} info accessors.
 *
 * Complements {@code ThreadBeadCycleFuzzProbe} (shape matrix, per-accessor
 * results, append, raw-pointer cycle walk, setters) by exercising the angles
 * that probe does not: forward ring ORDER over proper/broken/cyclic chains,
 * the backward {@code /V} chain order, {@code PDDocumentCatalog.getThreads()}
 * over malformed {@code /Threads} arrays (where PDFBox hard-casts every entry),
 * and {@code PDThread.getThreadInfo()} reading a {@code /Title} from {@code /I}.
 */
public final class ThreadBeadFuzzProbe {

    private interface Accessor {
        String get();
    }

    private static PrintStream out;

    private static String result(Accessor accessor) {
        try {
            return accessor.get();
        } catch (Throwable throwable) {
            return "ERR:" + throwable.getClass().getSimpleName();
        }
    }

    private static COSObject indirect(COSBase value) {
        return new COSObject(value);
    }

    private static COSDictionary node(String label) {
        COSDictionary dictionary = new COSDictionary();
        dictionary.setItem(COSName.TYPE, COSName.getPDFName("Bead"));
        dictionary.setItem(COSName.getPDFName("L"), new COSString(label));
        return dictionary;
    }

    private static String label(COSDictionary dictionary) {
        COSBase value = dictionary.getDictionaryObject(COSName.getPDFName("L"));
        if (value instanceof COSString) {
            return ((COSString) value).getString();
        }
        return "?";
    }

    // ---- forward ring order via /N, identity-guarded like PDFBox callers ----

    private static String forwardOrder(COSDictionary start) {
        IdentityHashMap<COSDictionary, Boolean> seen = new IdentityHashMap<>();
        StringBuilder order = new StringBuilder();
        PDThreadBead current = new PDThreadBead(start);
        while (true) {
            COSDictionary dictionary = current.getCOSObject();
            if (dictionary == null) {
                return order.append(order.length() > 0 ? "|" : "").append("wrap_null").toString();
            }
            if (seen.put(dictionary, Boolean.TRUE) != null) {
                return order.toString();
            }
            if (order.length() > 0) {
                order.append('-');
            }
            order.append(label(dictionary));
            PDThreadBead next = current.getNextBead();
            if (next == null) {
                return order.toString();
            }
            current = next;
        }
    }

    private static String backwardOrder(COSDictionary start) {
        IdentityHashMap<COSDictionary, Boolean> seen = new IdentityHashMap<>();
        StringBuilder order = new StringBuilder();
        PDThreadBead current = new PDThreadBead(start);
        while (true) {
            COSDictionary dictionary = current.getCOSObject();
            if (dictionary == null) {
                return order.append(order.length() > 0 ? "|" : "").append("wrap_null").toString();
            }
            if (seen.put(dictionary, Boolean.TRUE) != null) {
                return order.toString();
            }
            if (order.length() > 0) {
                order.append('-');
            }
            order.append(label(dictionary));
            PDThreadBead previous = current.getPreviousBead();
            if (previous == null) {
                return order.toString();
            }
            current = previous;
        }
    }

    private static int count(COSDictionary start) {
        IdentityHashMap<COSDictionary, Boolean> seen = new IdentityHashMap<>();
        PDThreadBead current = new PDThreadBead(start);
        while (true) {
            COSDictionary dictionary = current.getCOSObject();
            if (dictionary == null || seen.put(dictionary, Boolean.TRUE) != null) {
                return seen.size();
            }
            PDThreadBead next = current.getNextBead();
            if (next == null) {
                return seen.size();
            }
            current = next;
        }
    }

    private static void link(COSDictionary from, COSName key, COSDictionary to) {
        from.setItem(key, to);
    }

    private static void ringCases() {
        // proper 3-bead forward ring a -> b -> c -> a
        COSDictionary a = node("a");
        COSDictionary b = node("b");
        COSDictionary c = node("c");
        link(a, COSName.N, b);
        link(b, COSName.N, c);
        link(c, COSName.N, a);
        link(a, COSName.V, c);
        link(b, COSName.V, a);
        link(c, COSName.V, b);
        out.println("CASE ring_fwd " + result(() -> forwardOrder(a)));
        out.println("CASE ring_bwd " + result(() -> backwardOrder(a)));
        out.println("CASE ring_count " + result(() -> Integer.toString(count(a))));

        // broken chain: a -> b -> c, c has no /N (open list, not a ring)
        COSDictionary a2 = node("a");
        COSDictionary b2 = node("b");
        COSDictionary c2 = node("c");
        link(a2, COSName.N, b2);
        link(b2, COSName.N, c2);
        out.println("CASE broken_fwd " + result(() -> forwardOrder(a2)));
        out.println("CASE broken_count " + result(() -> Integer.toString(count(a2))));

        // cycle to the middle: a -> b -> c -> b (does not return to start)
        COSDictionary a3 = node("a");
        COSDictionary b3 = node("b");
        COSDictionary c3 = node("c");
        link(a3, COSName.N, b3);
        link(b3, COSName.N, c3);
        link(c3, COSName.N, b3);
        out.println("CASE cyclemid_fwd " + result(() -> forwardOrder(a3)));
        out.println("CASE cyclemid_count " + result(() -> Integer.toString(count(a3))));

        // self reference: a -> a
        COSDictionary a4 = node("a");
        link(a4, COSName.N, a4);
        out.println("CASE selfref_fwd " + result(() -> forwardOrder(a4)));
        out.println("CASE selfref_count " + result(() -> Integer.toString(count(a4))));

        // single bead, no /N at all
        COSDictionary a5 = node("a");
        out.println("CASE single_fwd " + result(() -> forwardOrder(a5)));
        out.println("CASE single_count " + result(() -> Integer.toString(count(a5))));

        // mid-chain /N points at a non-dictionary -> getNextBead returns null
        COSDictionary a6 = node("a");
        COSDictionary b6 = node("b");
        link(a6, COSName.N, b6);
        b6.setItem(COSName.N, COSInteger.ONE);
        out.println("CASE midwrong_fwd " + result(() -> forwardOrder(a6)));
        out.println("CASE midwrong_count " + result(() -> Integer.toString(count(a6))));

        // /N indirect across the ring (resolution must still close the ring)
        COSDictionary a7 = node("a");
        COSDictionary b7 = node("b");
        a7.setItem(COSName.N, indirect(b7));
        b7.setItem(COSName.N, indirect(a7));
        out.println("CASE indring_fwd " + result(() -> forwardOrder(a7)));
        out.println("CASE indring_count " + result(() -> Integer.toString(count(a7))));

        // backward broken: a <- nothing; a -> b -> c ring backward from c
        COSDictionary a8 = node("a");
        COSDictionary b8 = node("b");
        link(a8, COSName.V, b8);
        link(b8, COSName.V, a8);
        out.println("CASE bwd_two " + result(() -> backwardOrder(a8)));
    }

    // ---- catalog /Threads collection ----

    private static COSDictionary thread(String title) {
        COSDictionary dictionary = new COSDictionary();
        dictionary.setItem(COSName.TYPE, COSName.getPDFName("Thread"));
        COSDictionary info = new COSDictionary();
        info.setItem(COSName.getPDFName("Title"), new COSString(title));
        dictionary.setItem(COSName.I, info);
        return dictionary;
    }

    private static String threadsResult(PDDocument document, COSArray threadsArray) {
        document.getDocumentCatalog().getCOSObject()
                .setItem(COSName.getPDFName("Threads"), threadsArray);
        List<PDThread> threads = document.getDocumentCatalog().getThreads();
        StringBuilder value = new StringBuilder();
        value.append("n=").append(threads.size());
        for (PDThread thread : threads) {
            value.append(';');
            if (thread == null) {
                value.append("null");
                continue;
            }
            PDDocumentInformation info = thread.getThreadInfo();
            if (info == null) {
                value.append("noinfo");
            } else {
                value.append("title=").append(info.getTitle());
            }
        }
        return value.toString();
    }

    private static void threadsCases() throws Exception {
        try (PDDocument document = new PDDocument()) {
            // absent /Threads -> auto-created empty array
            document.getDocumentCatalog().getCOSObject()
                    .removeItem(COSName.getPDFName("Threads"));
            out.println("CASE threads_absent "
                    + result(() -> "n=" + document.getDocumentCatalog().getThreads().size()));
        }

        try (PDDocument document = new PDDocument()) {
            COSArray array = new COSArray();
            array.add(thread("One"));
            array.add(thread("Two"));
            out.println("CASE threads_two "
                    + result(() -> threadsResult(document, array)));
        }

        try (PDDocument document = new PDDocument()) {
            COSArray array = new COSArray();
            array.add(thread("One"));
            array.add(COSInteger.ONE); // non-dictionary entry
            array.add(thread("Three"));
            out.println("CASE threads_nondict "
                    + result(() -> threadsResult(document, array)));
        }

        try (PDDocument document = new PDDocument()) {
            COSArray array = new COSArray();
            array.add(thread("One"));
            array.add(COSNull.NULL); // explicit null entry
            out.println("CASE threads_null "
                    + result(() -> threadsResult(document, array)));
        }

        try (PDDocument document = new PDDocument()) {
            COSArray array = new COSArray();
            array.add(indirect(thread("Indirect")));
            out.println("CASE threads_indirect "
                    + result(() -> threadsResult(document, array)));
        }

        try (PDDocument document = new PDDocument()) {
            COSArray array = new COSArray();
            array.add(indirect(COSNull.NULL)); // dangling indirect -> resolves null
            out.println("CASE threads_dangling "
                    + result(() -> threadsResult(document, array)));
        }

        try (PDDocument document = new PDDocument()) {
            COSArray array = new COSArray();
            COSDictionary noInfo = new COSDictionary();
            noInfo.setItem(COSName.TYPE, COSName.getPDFName("Thread"));
            array.add(noInfo); // thread without /I
            out.println("CASE threads_noinfo "
                    + result(() -> threadsResult(document, array)));
        }
    }

    // ---- PDThread.getThreadInfo() over malformed /I ----

    private static void infoCases() {
        COSDictionary withTitle = new COSDictionary();
        COSDictionary info = new COSDictionary();
        info.setItem(COSName.getPDFName("Title"), new COSString("Hi"));
        withTitle.setItem(COSName.I, info);
        out.println("CASE info_title " + result(() -> {
            PDDocumentInformation pdi = new PDThread(withTitle).getThreadInfo();
            return pdi == null ? "null" : String.valueOf(pdi.getTitle());
        }));

        COSDictionary infoWrong = new COSDictionary();
        infoWrong.setItem(COSName.I, COSInteger.ONE);
        out.println("CASE info_wrong " + result(() -> {
            PDDocumentInformation pdi = new PDThread(infoWrong).getThreadInfo();
            return pdi == null ? "null" : "info";
        }));

        COSDictionary infoAbsent = new COSDictionary();
        out.println("CASE info_absent " + result(() -> {
            PDDocumentInformation pdi = new PDThread(infoAbsent).getThreadInfo();
            return pdi == null ? "null" : "info";
        }));
    }

    public static void main(String[] args) throws Exception {
        out = new PrintStream(System.out, true, "UTF-8");
        ringCases();
        threadsCases();
        infoCases();
    }
}
