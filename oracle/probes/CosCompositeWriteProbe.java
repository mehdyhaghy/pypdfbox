import java.io.ByteArrayOutputStream;
import java.io.PrintStream;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBoolean;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSObject;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.pdfwriter.COSWriter;

/**
 * Live oracle probe: emit the exact bytes Apache PDFBox's {@code COSWriter}
 * produces when serialising a COMPOSITE {@code COSDictionary} / {@code COSArray}
 * (the {@code << /Key Value ... >>} and {@code [ ... ]} self-write surface).
 *
 * This complements CosWriteSelfProbe / WriteScalarProbe / CosEscapeProbe, which
 * cover the per-scalar self-write + name/string escaping. Here the focus is the
 * COMPOSITE serialization decisions COSWriter alone owns:
 *
 *   - dictionary framing: {@code <<}, EOL, then per entry {@code /Key} SPACE
 *     value EOL, then {@code >>} EOL; entry order = COSDictionary insertion order
 *   - array framing: {@code [}, items separated by a single SPACE, with an EOL
 *     instead of a space after every 10th element, then {@code ]} EOL
 *   - mixed value types inline: name, int, real, string, boolean, null
 *   - nested direct dict / direct array
 *   - an indirect reference value -> {@code N G R}
 *   - the empty dict {@code << >>} and empty array {@code [ ]}
 *
 * In the standalone {@code visitFromDictionary} / {@code visitFromArray} path
 * COSWriter mints sequential object keys (1, 2, ...) for every indirect
 * reference it encounters, regardless of any pre-existing key on the referenced
 * object. The Python side mirrors this by constructing each {@code COSObject}
 * with object number 0 (which forces the writer to mint a fresh sequential
 * key), so the emitted {@code N G R} references line up byte-for-byte and the
 * test stays scoped to the COMPOSITE framing surface (not key-minting policy).
 *
 * COSWriter#visitFromDictionary / visitFromArray are public; the constructor
 * COSWriter(OutputStream) wires the standard-output framing layer to the
 * ByteArrayOutputStream we pass, so the composite bytes land there directly.
 *
 * Output: one {@code <label>: <hex>} line per case.
 *
 * Usage: java -cp <jar>:<build> CosCompositeWriteProbe
 */
public final class CosCompositeWriteProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");

        // --- empty dict / empty array.
        emit(out, "empty_dict", new COSDictionary());
        emit(out, "empty_array", new COSArray());

        // --- single-entry dict (name value).
        COSDictionary single = new COSDictionary();
        single.setItem(COSName.TYPE, COSName.getPDFName("Catalog"));
        emit(out, "single_dict", single);

        // --- array of mixed scalars (name, int, real, string, bool, null).
        COSArray scalars = new COSArray();
        scalars.add(COSName.getPDFName("Foo"));
        scalars.add(COSInteger.get(42));
        scalars.add(new COSFloat(3.14f));
        scalars.add(new COSString("hi"));
        scalars.add(COSBoolean.TRUE);
        scalars.add(COSBoolean.FALSE);
        scalars.add(null); // serialises as the keyword null
        emit(out, "scalar_array", scalars);

        // --- array that crosses the 10-element EOL boundary (12 ints) so the
        // every-10th-element newline rule is exercised.
        COSArray longArray = new COSArray();
        for (int i = 0; i < 12; i++) {
            longArray.add(COSInteger.get(i));
        }
        emit(out, "long_array", longArray);

        // --- nested array inside an array.
        COSArray nestedArrayOuter = new COSArray();
        COSArray inner = new COSArray();
        inner.add(COSInteger.get(1));
        inner.add(COSInteger.get(2));
        nestedArrayOuter.add(inner);
        nestedArrayOuter.add(COSInteger.get(3));
        emit(out, "nested_array", nestedArrayOuter);

        // --- a COMPOSITE dictionary with every value flavour, including a
        // nested direct dict, a nested direct array, and an indirect ref.
        COSDictionary composite = new COSDictionary();
        composite.setItem(COSName.TYPE, COSName.getPDFName("Page"));
        composite.setItem(COSName.COUNT, COSInteger.get(7));
        composite.setItem(COSName.getPDFName("Scale"), new COSFloat(0.5f));
        composite.setItem(COSName.getPDFName("Title"), new COSString("Hello (PDF)"));
        composite.setItem(COSName.getPDFName("Flag"), COSBoolean.TRUE);
        // nested DIRECT array.
        COSArray mediaBox = new COSArray();
        mediaBox.add(COSInteger.get(0));
        mediaBox.add(COSInteger.get(0));
        mediaBox.add(COSInteger.get(612));
        mediaBox.add(COSInteger.get(792));
        composite.setItem(COSName.getPDFName("MediaBox"), mediaBox);
        // INDIRECT dict value (default isDirect()==false) -> reference. In the
        // standalone visitFromDictionary path COSWriter#getObjectKey mints
        // sequential keys (1, 2, ...) regardless of any pre-stamped key, so
        // this is the FIRST minted reference -> "1 0 R".
        COSDictionary resources = new COSDictionary();
        resources.setItem(COSName.getPDFName("ProcSet"), COSName.getPDFName("PDF"));
        composite.setItem(COSName.RESOURCES, resources);
        // indirect reference value -> the SECOND minted reference -> "2 0 R".
        COSObject ref = new COSObject(new COSDictionary());
        composite.setItem(COSName.getPDFName("Parent"), ref);
        // explicit-null value: PDFBox skips null-valued entries entirely.
        composite.setItem(COSName.getPDFName("Skipped"), (org.apache.pdfbox.cos.COSBase) null);
        emit(out, "composite_dict", composite);

        // --- array whose elements are indirect references. Both mint
        // sequentially in the standalone path -> "1 0 R 2 0 R".
        COSArray refArray = new COSArray();
        refArray.add(new COSObject(new COSDictionary()));
        refArray.add(new COSObject(new COSArray()));
        emit(out, "ref_array", refArray);
    }

    private static void emit(PrintStream out, String label, COSDictionary dict)
            throws Exception {
        ByteArrayOutputStream baos = new ByteArrayOutputStream();
        COSWriter writer = new COSWriter(baos);
        writer.visitFromDictionary(dict);
        out.print(label + ": " + toHex(baos.toByteArray()) + "\n");
    }

    private static void emit(PrintStream out, String label, COSArray array)
            throws Exception {
        ByteArrayOutputStream baos = new ByteArrayOutputStream();
        COSWriter writer = new COSWriter(baos);
        writer.visitFromArray(array);
        out.print(label + ": " + toHex(baos.toByteArray()) + "\n");
    }

    private static String toHex(byte[] b) {
        StringBuilder sb = new StringBuilder();
        for (byte x : b) {
            sb.append(String.format("%02x", x & 0xff));
        }
        return sb.toString();
    }
}
