package tr.com.cmsrag.mcpswing.presentation;

import tr.com.cmsrag.mcpswing.application.TrackStateService;
import tr.com.cmsrag.mcpswing.domain.ShipType;
import tr.com.cmsrag.mcpswing.domain.TrackState;
import tr.com.cmsrag.mcpswing.domain.TrackStateChange;
import tr.com.cmsrag.mcpswing.domain.UpdateSource;
import javax.swing.*;
import javax.swing.table.DefaultTableModel;
import javax.swing.text.NumberFormatter;
import java.awt.*;
import java.text.NumberFormat;
import java.time.ZoneId;
import java.time.format.DateTimeFormatter;

/** Operatör değişiklikleriyle MCP değişikliklerini aynı ekranda görünür kılan Swing arayüzü. */
public final class TrackControlFrame extends JFrame {
    private static final Color NAVY = new Color(12, 31, 55);
    private static final Color BLUE = new Color(42, 105, 190);
    private static final Color BACKGROUND = new Color(241, 245, 249);
    private static final DateTimeFormatter TIME_FORMAT = DateTimeFormatter.ofPattern("HH:mm:ss");
    private final TrackStateService service;
    private final JFormattedTextField speedField = decimalField();
    private final JFormattedTextField headingField = integerField();
    private final JComboBox<ShipType> shipTypeBox = new JComboBox<>(ShipType.values());
    private final JCheckBox mcpWriteToggle = new JCheckBox("MCP / model yazma izni", true);
    private final DefaultTableModel historyModel = new DefaultTableModel(
            new Object[]{"#", "Saat", "Kaynak", "Değişiklik"}, 0) {
        @Override public boolean isCellEditable(int row, int column) { return false; }
    };
    private final JLabel statusLabel = new JLabel("Hazır", SwingConstants.LEFT);

    public TrackControlFrame(TrackStateService service) {
        super("CMS İz Kontrolü · MCP Swing Demo");
        this.service = service;
        setDefaultCloseOperation(WindowConstants.EXIT_ON_CLOSE);
        setMinimumSize(new Dimension(680, 600));
        setSize(820, 680);
        setLocationByPlatform(true);
        buildContent();
        renderState(service.getState(), "Başlangıç değerleri yüklendi");
        service.addListener(change -> SwingUtilities.invokeLater(() -> renderChange(change)));
    }

    private void buildContent() {
        JPanel root = new JPanel(new BorderLayout());
        root.setBackground(BACKGROUND);
        root.add(header(), BorderLayout.NORTH);
        JPanel workspace = new JPanel(new BorderLayout(0, 14));
        workspace.setBackground(BACKGROUND);
        workspace.setBorder(BorderFactory.createEmptyBorder(20, 26, 16, 26));
        workspace.add(form(), BorderLayout.NORTH);
        workspace.add(historyPanel(), BorderLayout.CENTER);
        root.add(workspace, BorderLayout.CENTER);
        root.add(statusBar(), BorderLayout.SOUTH);
        setContentPane(root);
    }

    private JPanel header() {
        JPanel panel = new JPanel(new BorderLayout());
        panel.setBackground(NAVY);
        panel.setBorder(BorderFactory.createEmptyBorder(22, 26, 22, 26));
        JLabel title = new JLabel("İZ DURUM KONTROLÜ");
        title.setForeground(Color.WHITE);
        title.setFont(title.getFont().deriveFont(Font.BOLD, 22f));
        JLabel subtitle = new JLabel("Yerel demonstrasyon · MCP araçlarıyla çift yönlü iletişim");
        subtitle.setForeground(new Color(190, 205, 224));
        subtitle.setBorder(BorderFactory.createEmptyBorder(7, 0, 0, 0));
        panel.add(title, BorderLayout.NORTH);
        panel.add(subtitle, BorderLayout.CENTER);
        return panel;
    }

    private JPanel form() {
        JPanel panel = new JPanel(new GridBagLayout());
        panel.setBackground(Color.WHITE);
        panel.setBorder(BorderFactory.createCompoundBorder(
                BorderFactory.createEmptyBorder(24, 26, 24, 26),
                BorderFactory.createLineBorder(new Color(216, 224, 235))));
        addRow(panel, 0, "Hız", speedField, "knot · 0–100");
        addRow(panel, 1, "Yön", headingField, "derece · 0–360");
        addRow(panel, 2, "İz / gemi tipi", shipTypeBox, "kontrollü sınıflandırma");
        mcpWriteToggle.setBackground(Color.WHITE);
        mcpWriteToggle.setForeground(NAVY);
        mcpWriteToggle.setToolTipText("Kapalıyken MCP okuma araçları çalışır, yazma araçları reddedilir.");
        mcpWriteToggle.addActionListener(event -> updateWritePolicy());
        GridBagConstraints toggle = constraints(1, 3);
        toggle.gridwidth = 2;
        toggle.insets = new Insets(12, 16, 2, 0);
        panel.add(mcpWriteToggle, toggle);
        JButton applyButton = new JButton("Değerleri Uygula");
        applyButton.setBackground(BLUE);
        applyButton.setForeground(Color.WHITE);
        applyButton.setFocusPainted(false);
        applyButton.setFont(applyButton.getFont().deriveFont(Font.BOLD, 14f));
        applyButton.addActionListener(event -> applyForm());
        GridBagConstraints button = constraints(1, 4);
        button.anchor = GridBagConstraints.EAST;
        button.insets = new Insets(20, 8, 0, 0);
        panel.add(applyButton, button);
        return panel;
    }

    private JPanel historyPanel() {
        JPanel panel = new JPanel(new BorderLayout());
        panel.setBackground(Color.WHITE);
        panel.setBorder(BorderFactory.createTitledBorder(
                BorderFactory.createLineBorder(new Color(216, 224, 235)), " İşlem Geçmişi "));
        JTable table = new JTable(historyModel);
        table.setFillsViewportHeight(true);
        table.setRowHeight(25);
        table.getColumnModel().getColumn(0).setMaxWidth(45);
        table.getColumnModel().getColumn(1).setMaxWidth(80);
        table.getColumnModel().getColumn(2).setPreferredWidth(105);
        table.getColumnModel().getColumn(3).setPreferredWidth(480);
        panel.add(new JScrollPane(table), BorderLayout.CENTER);
        return panel;
    }

    private JPanel statusBar() {
        JPanel panel = new JPanel(new BorderLayout());
        panel.setBackground(BACKGROUND);
        panel.setBorder(BorderFactory.createEmptyBorder(13, 26, 15, 26));
        statusLabel.setForeground(new Color(55, 72, 94));
        panel.add(statusLabel, BorderLayout.CENTER);
        return panel;
    }

    private void addRow(JPanel panel, int row, String label, Component input, String hint) {
        JLabel fieldLabel = new JLabel(label);
        fieldLabel.setForeground(NAVY);
        fieldLabel.setFont(fieldLabel.getFont().deriveFont(Font.BOLD, 14f));
        panel.add(fieldLabel, constraints(0, row));
        GridBagConstraints inputConstraints = constraints(1, row);
        inputConstraints.weightx = 1.0;
        inputConstraints.fill = GridBagConstraints.HORIZONTAL;
        inputConstraints.insets = new Insets(9, 16, 9, 10);
        panel.add(input, inputConstraints);
        JLabel hintLabel = new JLabel(hint);
        hintLabel.setForeground(new Color(100, 116, 139));
        panel.add(hintLabel, constraints(2, row));
    }

    private void applyForm() {
        try {
            speedField.commitEdit();
            headingField.commitEdit();
            service.setState(((Number) speedField.getValue()).doubleValue(),
                    ((Number) headingField.getValue()).intValue(),
                    (ShipType) shipTypeBox.getSelectedItem(), UpdateSource.OPERATOR);
        } catch (Exception exception) {
            statusLabel.setForeground(new Color(185, 28, 28));
            statusLabel.setText("⚠ " + exception.getMessage());
        }
    }

    private void updateWritePolicy() {
        boolean enabled = mcpWriteToggle.isSelected();
        service.setMcpWritesEnabled(enabled);
        statusLabel.setForeground(enabled ? new Color(21, 128, 61) : new Color(185, 28, 28));
        statusLabel.setText(enabled
                ? "✓ MCP yazma işlemleri operatör tarafından etkinleştirildi"
                : "🔒 MCP yazma işlemleri kilitlendi; okuma araçları açık");
    }

    private void renderChange(TrackStateChange change) {
        renderState(change.after(), null);
        historyModel.insertRow(0, new Object[]{
                change.sequence(),
                TIME_FORMAT.format(change.occurredAt().atZone(ZoneId.systemDefault())),
                change.source().displayName(),
                change.summary()
        });
        while (historyModel.getRowCount() > 100) historyModel.removeRow(100);
        boolean fromMcp = change.source() == UpdateSource.MCP;
        statusLabel.setForeground(fromMcp ? BLUE : new Color(21, 128, 61));
        statusLabel.setText(fromMcp
                ? "✓ MCP/model güncellemesi uygulandı ve geri okunabilir"
                : "✓ Operatör güncellemesi doğrulandı ve uygulandı");
    }

    private void renderState(TrackState state, String message) {
        speedField.setValue(state.speedKnots());
        headingField.setValue(state.headingDegrees());
        shipTypeBox.setSelectedItem(state.shipType());
        if (message != null) {
            statusLabel.setForeground(new Color(55, 72, 94));
            statusLabel.setText(message);
        }
    }

    private static GridBagConstraints constraints(int column, int row) {
        GridBagConstraints value = new GridBagConstraints();
        value.gridx = column; value.gridy = row; value.anchor = GridBagConstraints.WEST;
        value.insets = new Insets(9, 0, 9, 0);
        return value;
    }

    private static JFormattedTextField decimalField() {
        NumberFormat format = NumberFormat.getNumberInstance();
        format.setMaximumFractionDigits(2);
        NumberFormatter formatter = new NumberFormatter(format);
        formatter.setValueClass(Double.class); formatter.setAllowsInvalid(true);
        return formattedField(formatter);
    }
    private static JFormattedTextField integerField() {
        NumberFormat format = NumberFormat.getIntegerInstance(); format.setGroupingUsed(false);
        NumberFormatter formatter = new NumberFormatter(format);
        formatter.setValueClass(Integer.class); formatter.setAllowsInvalid(true);
        return formattedField(formatter);
    }
    private static JFormattedTextField formattedField(NumberFormatter formatter) {
        JFormattedTextField field = new JFormattedTextField(formatter);
        field.setColumns(12); field.setPreferredSize(new Dimension(180, 36));
        return field;
    }
}
