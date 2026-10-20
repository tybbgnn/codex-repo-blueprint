// Single declarative registry. Keep the export JSON-compatible for the Python proof service.
export default {
  "version": 1,
  "technicalCategories": [
    "cleanup",
    "unwind",
    "drop",
    "state_dispatch",
    "async_mechanism",
    "instrumentation"
  ],
  "roles": {
    "body": {
      "kinds": [
        "direct",
        "async-shell"
      ],
      "executionForms": [
        "sync",
        "coroutine"
      ],
      "mappingModes": [
        "strict-forward",
        "retained-relation"
      ]
    },
    "block": {
      "kinds": [
        "business",
        "span_wrapper",
        "event_macro",
        "routing",
        "compiler_artifact",
        "async_protocol"
      ],
      "technicalCategoryMap": {
        "cleanup": "compiler_artifact",
        "unwind": "compiler_artifact",
        "drop": "compiler_artifact",
        "state_dispatch": "compiler_artifact",
        "async_mechanism": "async_protocol",
        "instrumentation": "span_wrapper"
      }
    },
    "operation": {
      "kinds": [
        "business",
        "proven_drop_flag",
        "compiler_bookkeeping",
        "unit_context_or_signature"
      ]
    },
    "attributes": {
      "action.loopHandoff": {
        "values": [true],
        "consumers": [
          "G2",
          "G10",
          "P14"
        ]
      },
      "loop.exitMode": {
        "values": [
          "commonAfter",
          "terminalOnly"
        ],
        "consumers": {
          "commonAfter": [
            "P11"
          ],
          "terminalOnly": [
            "P11",
            "renderer_contract"
          ]
        }
      }
    }
  },
  "exceptions": {
    "pure_loop_handoff": {
      "consumers": [
        "G2",
        "G10",
        "P14"
      ],
      "proof": "prove_handoff",
      "allows": [
        "independent_fact_exception",
        "empty_detail_snippets"
      ],
      "forbids": [
        "standalone_goal"
      ]
    },
    "instrumentation": {
      "consumers": [
        "G10",
        "technical_boundary",
        "resolver"
      ],
      "proof": "instrumentation_record_valid",
      "required": [
        "bbRef",
        "reason",
        "evidenceRefs",
        "factSha256"
      ],
      "proofKinds": [
        "sync_instrumentation",
        "async_instrumentation"
      ]
    },
    "source_less": {
      "consumers": [
        "P14",
        "source_ranges",
        "renderer_contract"
      ],
      "required": [
        "basicBlockRefs",
        "sourceRangeReason"
      ],
      "proof": "shape_only",
      "detailException": "pure_loop_handoff"
    }
  },
  "instrumentationProofs": {
    "sync_instrumentation": {
      "function": "prove_sync",
      "purpose": "technical_blocks"
    },
    "async_instrumentation": {
      "function": "prove_async",
      "purpose": "technical_blocks"
    },
    "async_forwarding": {
      "function": "prove",
      "purpose": "resolver_identity"
    }
  }
};
