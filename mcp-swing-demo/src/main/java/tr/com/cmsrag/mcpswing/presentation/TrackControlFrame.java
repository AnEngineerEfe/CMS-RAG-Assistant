package tr.com.cmsrag.mcpswing.presentation;

import tr.com.cmsrag.mcpswing.application.TrackStateService;
import tr.com.cmsrag.mcpswing.domain.ShipType;
import tr.com.cmsrag.mcpswing.domain.TrackState;
import javax.swing.*;
import javax.swing.text.NumberFormatter;
import java.awt.*;
import java.text.NumberFormat;

/** Operatör değişiklikleriyle MCP değişikliklerini aynı ekranda görünür kılan Swing arayüzü. */
public final class TrackControlFrame extends JFrame {
    private static final Color NAVY = new Color(12, 31, 55);
    private static final Color BLUE = new Color(42, 105, 190);
    private static final Color BACKGROUND = new Color(241, 245, 249);
    private final TrackStateService service;
    private final JFormattedTextField speedField = decimalField();
    private final JFormattedTextField headingField = integerField();
    private final JComboBox<ShipType> shipTypeBox = new JComboBox<>(ShipType.values());
    private final JLabel statusLabel = new JLabel("Hazır", SwingConstants.LEFT);

    public TrackControlFrame(TrackStateService service) {
        super("CMS İz Kontrolü · MCP Swing Demo");
        this.service = service;
        setDefaultCloseOperation(WindowConstants.EXIT_ON_CLOSE);
        setMinimumSize(new Dimension(560, 430));
        setSize(620, 470);
        setLocationByPlatform(true);
        buildContent();
        renderState(service.getState(), "Başlangıç değerleri yüklendi");
        service.addListener(state -> SwingUtilities.invokeLater(
                () -> renderState(state, "Değerler MCP veya arayüz üzerinden güncellendi")));
    }

    private void buildContent() {
        JPanel root = new JPanel(new BorderLayout());
        root.setBackground(BACKGROUND);
        root.add(header(), BorderLayout.NORTH);
        root.add(form(), BorderLayout.CENTER);
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
        JButton applyButton = new JButton("Değerleri Uygula");
        applyButton.setBackground(BLUE);
        applyButton.setForeground(Color.WHITE);
        applyButton.setFocusPainted(false);
        applyButton.setFont(applyButton.getFont().deriveFont(Font.BOLD, 14f));
        applyButton.addActionListener(event -> applyForm());
        GridBagConstraints button = constraints(1, 3);
        button.anchor = GridBagConstraints.EAST;
        button.insets = new Insets(20, 8, 0, 0);
        panel.add(applyButton, button);
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
                    (ShipType) shipTypeBox.getSelectedItem());
            statusLabel.setForeground(new Color(21, 128, 61));
            statusLabel.setText("✓ Değerler doğrulandı ve ortak duruma uygulandı");
        } catch (Exception exception) {
            statusLabel.setForeground(new Color(185, 28, 28));
            statusLabel.setText("⚠ " + exception.getMessage());
        }
    }

    private void renderState(TrackState state, String message) {
        speedField.setValue(state.speedKnots());
        headingField.setValue(state.headingDegrees());
        shipTypeBox.setSelectedItem(state.shipType());
        statusLabel.setForeground(new Color(55, 72, 94));
        statusLabel.setText(message);
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
