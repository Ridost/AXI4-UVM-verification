class axi4_driver extends uvm_driver #(axi4_txn);

  virtual axi4_if.master vif;

  `uvm_component_utils(axi4_driver)

  task run_phase(uvm_phase phase);
  
    axi4_txn txn;
  
    forever begin
      seq_item_port.get_next_item(txn);
  
      if (txn.is_write)
        drive_write(txn);
      else
        drive_read(txn);
  
      seq_item_port.item_done();
    end
  
  endtask

  task drive_aw(axi4_txn txn);

    @(posedge vif.ACLK);
  
    vif.AWID    <= txn.id;
    vif.AWADDR  <= txn.addr;
    vif.AWLEN   <= txn.len;
    vif.AWSIZE  <= txn.size;
    vif.AWBURST <= txn.burst;
    vif.AWVALID <= 1;
  
    // handshake
    wait (vif.AWREADY);
  
    @(posedge vif.ACLK);
    vif.AWVALID <= 0;
  
  endtask
  task drive_w(axi4_txn txn);

    for (int i = 0; i < txn.len + 1; i++) begin
  
      @(posedge vif.ACLK);
  
      vif.WDATA  <= txn.data[i];
      vif.WSTRB  <= txn.strb[i];
      vif.WLAST  <= (i == txn.len);
      vif.WVALID <= 1;
  
      wait (vif.WREADY);
  
    end
  
    @(posedge vif.ACLK);
    vif.WVALID <= 0;
  
  endtask
  task drive_b(axi4_txn txn);

    vif.BREADY <= 1;
  
    wait (vif.BVALID);
  
    txn.resp = new[1];
    txn.resp[0] = vif.BRESP;
  
    @(posedge vif.ACLK);
    vif.BREADY <= 0;
  
  endtask

  task drive_write(axi4_txn txn);

    drive_aw(txn);
    drive_w(txn);
    drive_b(txn);
  
  endtask

  task drive_ar(axi4_txn txn);

    @(posedge vif.ACLK);
  
    vif.ARID    <= txn.id;
    vif.ARADDR  <= txn.addr;
    vif.ARLEN   <= txn.len;
    vif.ARSIZE  <= txn.size;
    vif.ARBURST <= txn.burst;
    vif.ARVALID <= 1;
  
    wait (vif.ARREADY);
  
    @(posedge vif.ACLK);
    vif.ARVALID <= 0;
  
  endtask
  task drive_r(axi4_txn txn);

    txn.data = new[txn.len + 1];
    txn.resp = new[txn.len + 1];
  
    vif.RREADY <= 1;
  
    for (int i = 0; i < txn.len + 1; i++) begin
  
      wait (vif.RVALID);
  
      txn.data[i] = vif.RDATA;
      txn.resp[i] = vif.RRESP;
  
      if (vif.RLAST && i != txn.len)
        `uvm_error("AXI", "Unexpected RLAST")
  
      @(posedge vif.ACLK);
    end
  
    vif.RREADY <= 0;
  
  endtask
  task drive_read(axi4_txn txn);

    drive_ar(txn);
    drive_r(txn);
  
  endtask
endclass
