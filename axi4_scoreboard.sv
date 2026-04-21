class axi4_scoreboard extends uvm_component;

  uvm_analysis_imp #(axi4_txn, axi4_scoreboard) imp;

  // byte-level memory
  bit [7:0] mem [bit [ADDR_WIDTH-1:0]];

  `uvm_component_utils(axi4_scoreboard)
  
  function void write(axi4_txn txn);

    if (txn.is_write)
      handle_write(txn);
    else
      handle_read(txn);
  
  endfunction
  function void handle_write(axi4_txn txn);
  
    int beats = txn.len + 1;
    int bytes_per_beat = 1 << txn.size;
  
    for (int i = 0; i < beats; i++) begin
  
      bit [ADDR_WIDTH-1:0] base_addr;
      base_addr = txn.addr + (i * bytes_per_beat);
  
      for (int b = 0; b < bytes_per_beat; b++) begin
  
        if (txn.strb[i][b]) begin
  
          mem[base_addr + b] = txn.data[i][8*b +: 8];
  
        end
  
      end
    end
  
    `uvm_info("SCB", $sformatf("WRITE @0x%0h len=%0d", txn.addr, txn.len), UVM_LOW)
  
  endfunction
  function void handle_read(axi4_txn txn);
  
    int beats = txn.len + 1;
    int bytes_per_beat = 1 << txn.size;
  
    for (int i = 0; i < beats; i++) begin
  
      bit [ADDR_WIDTH-1:0] base_addr;
      base_addr = txn.addr + (i * bytes_per_beat);
  
      bit [DATA_WIDTH-1:0] expected = '0;
  
      for (int b = 0; b < bytes_per_beat; b++) begin
  
        if (mem.exists(base_addr + b))
          expected[8*b +: 8] = mem[base_addr + b];
        else
          expected[8*b +: 8] = '0; // default value
  
      end
  
      if (expected !== txn.data[i]) begin
  
        `uvm_error("SCB",
          $sformatf("READ MISMATCH @0x%0h beat=%0d exp=0x%0h act=0x%0h",
                    base_addr, i, expected, txn.data[i]))
  
      end
      else begin
        `uvm_info("SCB",
          $sformatf("READ OK @0x%0h data=0x%0h",
                    base_addr, txn.data[i]),
          UVM_HIGH)
      end
      
    end
  
  endfunction
endclass
