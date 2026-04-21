class axi4_monitor extends uvm_monitor;

  virtual axi4_if.monitor vif;

  uvm_analysis_port #(axi4_txn) ap;

  `uvm_component_utils(axi4_monitor)

  task run_phase(uvm_phase phase);

    forever begin
  
      axi4_txn txn;
  
      @(posedge vif.ACLK);
  
      if (vif.AWVALID && vif.AWREADY) begin
        txn = collect_write();
        ap.write(txn);
      end
      else if (vif.ARVALID && vif.ARREADY) begin
        txn = collect_read();
        ap.write(txn);
      end
      `uvm_info("MON", txn.convert2string(), UVM_MEDIUM)
    end
  endtask
  function axi4_txn collect_write();
  
    axi4_txn txn = axi4_txn::type_id::create("txn");
  
    // -------------------------
    // AW
    // -------------------------
    txn.is_write = 1;
    txn.id   = vif.AWID;
    txn.addr = vif.AWADDR;
    txn.len  = vif.AWLEN;
    txn.size = vif.AWSIZE;
    txn.burst= vif.AWBURST;
  
    int beats = txn.len + 1;
  
    txn.data = new[beats];
    txn.strb = new[beats];
  
    // -------------------------
    // W
    // -------------------------
    for (int i = 0; i < beats; i++) begin

      wait (vif.WVALID && vif.WREADY);
  
      txn.data[i] = vif.WDATA;
      txn.strb[i] = vif.WSTRB;
  
      if (vif.WLAST && i != beats-1)
        `uvm_error("MON", "Unexpected WLAST")
  
      @(posedge vif.ACLK);
    end
  
    // -------------------------
    // B
    // -------------------------
    wait (vif.BVALID && vif.BREADY);
  
    txn.resp = new[1];
    txn.resp[0] = vif.BRESP;
  
    @(posedge vif.ACLK);
  
    return txn;
  
  endfunction
  function axi4_txn collect_read();
  
    axi4_txn txn = axi4_txn::type_id::create("txn");
  
    // -------------------------
    // AR
    // -------------------------
    txn.is_write = 0;
    txn.id   = vif.ARID;
    txn.addr = vif.ARADDR;
    txn.len  = vif.ARLEN;
    txn.size = vif.ARSIZE;
    txn.burst= vif.ARBURST;
  
    int beats = txn.len + 1;
  
    txn.data = new[beats];
    txn.resp = new[beats];
  
    // -------------------------
    // R
    // -------------------------
    for (int i = 0; i < beats; i++) begin
  
      wait (vif.RVALID && vif.RREADY);
  
      txn.data[i] = vif.RDATA;
      txn.resp[i] = vif.RRESP;
  
      if (vif.RLAST && i != beats-1)
        `uvm_error("MON", "Unexpected RLAST")
  
      @(posedge vif.ACLK);
    end
  
    return txn;
  
  endfunction
  
endclass
