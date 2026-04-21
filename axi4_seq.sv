class axi4_base_seq extends uvm_sequence #(axi4_txn);

  rand int num_txn;

  constraint c_num {
    num_txn inside {[10:50]};
  }

  `uvm_object_utils(axi4_base_seq)

endclass

class axi4_write_seq extends axi4_base_seq;

  `uvm_object_utils(axi4_write_seq)

  task body();
    axi4_txn txn;

    repeat (num_txn) begin

      txn = axi4_txn::type_id::create("txn");

      start_item(txn);

      assert(txn.randomize() with {
        is_write == 1;

        len inside {[0:7]};

        addr % (1 << size) == 0;
      });

      finish_item(txn);

    end
  endtask

endclass

class axi4_read_seq extends axi4_base_seq;

  `uvm_object_utils(axi4_read_seq)

  task body();
    axi4_txn txn;

    repeat (num_txn) begin

      txn = axi4_txn::type_id::create("txn");

      start_item(txn);

      assert(txn.randomize() with {
        is_write == 0;

        len inside {[0:7]};
        addr % (1 << size) == 0;
      });

      finish_item(txn);

    end
  endtask

endclass

class axi4_mixed_seq extends axi4_base_seq;

  rand bit [31:0] write_ratio; // %

  constraint c_ratio {
    write_ratio inside {[30:70]};
  }

  `uvm_object_utils(axi4_mixed_seq)

  task body();
    axi4_txn txn;

    repeat (num_txn) begin

      txn = axi4_txn::type_id::create("txn");

      start_item(txn);

      assert(txn.randomize() with {

        is_write dist {
          1 := write_ratio,
          0 := (100 - write_ratio)
        };

        len inside {[0:15]};

        addr % (1 << size) == 0;

      });

      finish_item(txn);

    end
  endtask

endclass
