import java.io.ByteArrayInputStream;
import java.util.ArrayList;

import javax.imageio.stream.ImageInputStream;
import javax.imageio.stream.MemoryCacheImageInputStream;

import org.apache.pdfbox.jbig2.decoder.huffman.HuffmanTable;
import org.apache.pdfbox.jbig2.decoder.huffman.StandardTables;

/**
 * Differential oracle probe for the JBIG2 Huffman entropy coder.
 *
 * Usage: HuffmanProbe <tableNumber 1..15> <hexbytes> <count>
 *
 * Builds StandardTables.getTable(tableNumber), then decodes <count> values from
 * the supplied big-endian bit stream, printing one decoded value per line.
 * Long.MAX_VALUE (the out-of-band sentinel) is printed verbatim.
 */
public class HuffmanProbe
{
    public static void main(String[] args) throws Exception
    {
        int tableNumber = Integer.parseInt(args[0]);
        byte[] data = hexToBytes(args[1]);
        int count = Integer.parseInt(args[2]);

        HuffmanTable table = StandardTables.getTable(tableNumber);

        ImageInputStream iis =
                new MemoryCacheImageInputStream(new ByteArrayInputStream(data));

        ArrayList<String> out = new ArrayList<String>();
        for (int i = 0; i < count; i++)
        {
            long v = table.decode(iis);
            out.add(Long.toString(v));
        }

        StringBuilder sb = new StringBuilder();
        for (String s : out)
        {
            sb.append(s).append("\n");
        }
        System.out.print(sb.toString());
    }

    private static byte[] hexToBytes(String hex)
    {
        int n = hex.length() / 2;
        byte[] b = new byte[n];
        for (int i = 0; i < n; i++)
        {
            b[i] = (byte) Integer.parseInt(hex.substring(2 * i, 2 * i + 2), 16);
        }
        return b;
    }
}
